"""Offline form build checks; fixture data are not research results."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from review_ui import build_review_html
from review_key_codec import to_human_reviews, to_technical_reviews


ROOT = Path(__file__).resolve().parents[1]


def payload(html, element_id):
    match = re.search(r'<script id="' + element_id + r'" type="application/json">(.*?)</script>',
                      html, re.S)
    if not match:
        raise AssertionError("Missing JSON element: " + element_id)
    return json.loads(match.group(1))


class ReviewHtmlBuildTests(unittest.TestCase):
    def minimal_package(self, destination):
        destination = Path(destination)
        for relative in ["web/review_app.js", "web/review_keys.js", "web/review_app.css", "schemas/review_key_map.json"]:
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, path)
        observer = next(iter(sorted((ROOT / "prospective/observer_inputs").glob("*.json"))))
        target = destination / "prospective/observer_inputs" / observer.name
        target.parent.mkdir(parents=True)
        shutil.copy2(observer, target)
        return destination, target

    def test_builder_reads_observer_data_and_key_rules_without_review_content(self):
        with tempfile.TemporaryDirectory() as td:
            root, source = self.minimal_package(td)
            (root / "REVIEWS.json").write_text('{"label":"PRIVATE_REVIEW_SENTINEL"}', encoding="utf-8")
            (root / "wording").mkdir()
            (root / "wording/Tier_S_Wording_Alternatives.json").write_text(
                '{"suggestion":"PRIVATE_WORDING_SENTINEL"}', encoding="utf-8")
            html = build_review_html(root).read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE_REVIEW_SENTINEL", html)
            self.assertNotIn("PRIVATE_WORDING_SENTINEL", html)
            data = payload(html, "observer-data")
            self.assertEqual(len(data["cases"]), 1)
            case = data["cases"][0]
            self.assertEqual(set(case), {"case_id", "observer_input_sha256", "observer_input"})
            self.assertEqual(case["observer_input"], json.loads(source.read_text()))
            self.assertEqual(set(case["observer_input"]),
                             {"overall_task", "participants", "context_sources", "dialogue_prefix"})
            self.assertEqual(case["observer_input_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            mapping = payload(html, "review-key-map-data")
            self.assertEqual(set(mapping), {"format_id", "maps", "children", "field_reference_lists"})
            expected = json.loads((root / "schemas/review_key_map.json").read_text())
            self.assertEqual(mapping, {key: expected[key] for key in mapping})
            self.assertNotIn('id="field-map-data"', html)
            self.assertIn((root / "web/review_keys.js").read_text(), html)

    def test_key_map_data_cannot_close_its_json_script(self):
        with tempfile.TemporaryDirectory() as td:
            root, _ = self.minimal_package(td)
            path = root / "schemas/review_key_map.json"
            mapping = json.loads(path.read_text())
            special = '</script><script>KEY_FIXTURE</script>\u2028\u2029'
            mapping["maps"]["review"]["reviewer_id"] = special
            path.write_text(json.dumps(mapping), encoding="utf-8")
            html = build_review_html(root).read_text(encoding="utf-8")
            self.assertNotIn(special, html)
            self.assertEqual(payload(html, "review-key-map-data")["maps"]["review"]["reviewer_id"], special)

    def test_duplicate_labels_reject_ambiguous_key_map(self):
        with tempfile.TemporaryDirectory() as td:
            root, _ = self.minimal_package(td)
            path = root / "schemas/review_key_map.json"
            mapping = json.loads(path.read_text())
            mapping["maps"]["review"]["reviewer_id"] = mapping["maps"]["review"]["review_status"]
            path.write_text(json.dumps(mapping), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Ambiguous human review key"):
                build_review_html(root)
            self.assertFalse((root / "REVIEW.html").exists())


@unittest.skipUnless(shutil.which("node"), "Node is required for cross-language codec checks")
class ReviewKeyBrowserParityTests(unittest.TestCase):
    def node_result(self, data, direction):
        script = """
const fs = require('node:fs');
const {createCodec} = require(process.argv[1]);
const codec = createCodec(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')));
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(codec[input.direction](input.data)));
"""
        return subprocess.run(["node", "-e", script, str(ROOT / "web/review_keys.js"),
                               str(ROOT / "schemas/review_key_map.json")],
                              input=json.dumps({"data": data, "direction": direction}),
                              text=True, capture_output=True)

    def node_value(self, data, direction):
        result = self.node_result(data, direction)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_actual_reviews_roundtrip_with_canonical_hash_and_note_parity(self):
        raw = json.loads((ROOT / "REVIEWS.json").read_text(encoding="utf-8"))
        technical = to_technical_reviews(raw)
        human = to_human_reviews(technical)
        self.assertEqual(self.node_value(technical, "toHumanReviews"), human)
        returned = self.node_value(human, "toTechnicalReviews")
        self.assertEqual(returned, technical)
        canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":"), allow_nan=False).encode()
        self.assertEqual(hashlib.sha256(canonical(returned)).hexdigest(),
                         hashlib.sha256(canonical(technical)).hexdigest())
        mt10 = next(key for key in technical if key.startswith("MT10_"))
        self.assertIs(returned[mt10]["blocking_uncertainty"], False)
        self.assertEqual(returned[mt10]["provisional_label"], "ALIGNED")
        for case_id, record in technical.items():
            self.assertEqual(returned[case_id]["review_metadata"], record["review_metadata"])
            self.assertEqual(returned[case_id]["participant_meanings_with_source_quotes"],
                             record["participant_meanings_with_source_quotes"])

    def test_snapshots_field_references_and_opaque_values_match_python(self):
        data = {"fixture": {
            "reviewer_id": "fixture-only",
            "review_metadata": {
                "assistant_wording_fields": ["local_question", "prefix_only_rationale"],
                "first_pass_judgment_snapshot": {"reviewer_id": "initial", "local_question": "Unchanged question"},
                "first_pass_judgment_sha256": "preserved-digest",
                "wording_exposure_events": [{"fields": ["local_question"], "action": "copy_prose"}],
                "unknown_history": {"Reviewer": "Keep unknown nested key", "reviewer_id": "Keep this too"}},
            "task_outputs": {"participant_outputs": {"Review judgment": "Dynamic participant ID"},
                             "supported_consequences": {"person": [{"meaning": "Opaque key"}]}},
            "participant_meanings_with_source_quotes": [{"participant_id": "person", "support_note": "Existing note", "source_quotes": [{"source_id": "t1", "quote": "Review judgment", "speaker": "person"}]}]
        }}
        human = to_human_reviews(data)
        self.assertEqual(self.node_value(data, "toHumanReviews"), human)
        self.assertEqual(self.node_value(human, "toTechnicalReviews"), data)
        self.assertEqual(to_technical_reviews(human), data)

    def test_both_codecs_reject_equal_value_alias_collisions(self):
        cases = [
            {"fixture": {"reviewer_id": "x", "Reviewer": "x"}},
            {"fixture": {"review_metadata": {"assistant_wording_fields": ["local_question", "Local task question"]}}},
            {"fixture": {"review_metadata": {"first_pass_judgment_snapshot": {"reviewer_id": "x", "Reviewer": "x"}}}},
        ]
        for data in cases:
            with self.subTest(data=data):
                for function in [to_human_reviews, to_technical_reviews]:
                    with self.assertRaises(ValueError):
                        function(data)
                for direction in ["toHumanReviews", "toTechnicalReviews"]:
                    result = self.node_result(data, direction)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Ambiguous", result.stderr)


if __name__ == "__main__":
    unittest.main()
