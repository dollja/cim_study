"""Evidence-boundary and provenance checks for pending human review files."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import review_tools as rt
import pilot


class ReviewToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.observer_dir = self.base / "observer_inputs"
        self.observer_dir.mkdir()
        self.rows = [
            {"utterance_id": "CASE_A.row.001", "speaker": "giver", "text": "Pass below bridge B."},
            {"utterance_id": "CASE_A.row.002", "speaker": "follower", "text": "I will pass below bridge B."},
            {"utterance_id": "CASE_A.row.003", "speaker": "Audio", "text": "Stop."},
        ]
        self.observer = {
            "overall_task": "Follow a route.",
            "participants": [{"participant_id": "giver", "known_role": "giver"},
                             {"participant_id": "follower", "known_role": "follower"},
                             {"participant_id": "Audio", "known_role": "recorded_audio_not_player"}],
            "context_sources": [], "dialogue_prefix": self.rows,
        }
        rt.write_new(self.observer_dir / "CASE_A.json", self.observer)
        rt.write_new(self.base / "curator_cases" / "CASE_A.json", {
            "sampling_and_reference_protocol": {"provisional_source_group": "map_demo"}})
        self.legacy = {"CASE_A": {
            "review_status": "in_progress", "reviewer_id": "r1",
            "assistant_draft_seen_before_judgment": True,
            "prefix_first_review_completed": False, "later_evidence_review_completed": False,
            "focal_pair": None, "local_question": None, "focus_source_ids": [],
            "participant_meanings_with_source_quotes": [], "task_outputs": None,
            "blocking_uncertainty": None, "provisional_label": None,
            "evidence_verified": None, "include_in_pilot": None,
            "inclusion_or_exclusion_reason": None,
        }}
        self.outcome = {"kind": "Route", "event": "step1", "relation": "below", "anchor": "bridge_B"}

    def blank(self, reviewer="r1"):
        return rt.migrate_reviews(self.legacy, self.observer_dir, blank=True, reviewer_id=reviewer)

    def complete(self, reviewer="r1"):
        reviews = self.blank(reviewer)
        r = reviews["CASE_A"]
        r.update(review_status="reviewed", focal_pair=["giver", "follower"],
                 local_question="Which side of bridge B should the route use?",
                 focus_source_ids=[row["utterance_id"] for row in self.rows[:2]],
                 focus_quotes=[{"source_id": row["utterance_id"], "speaker": row["speaker"],
                                "quote": row["text"]} for row in self.rows[:2]],
                 participant_meanings_with_source_quotes=[{
                     "participant_id": row["speaker"], "meaning": "The route passes below bridge B.",
                     "source_quotes": [{"source_id": row["utterance_id"], "quote": row["text"]}],
                     "support": "supported"} for row in self.rows[:2]],
                 task_outputs={"scope": "Route step 1", "supported_consequences": {
                     "giver": [deepcopy(self.outcome)], "follower": [deepcopy(self.outcome)]}},
                 blocking_uncertainty=False, provisional_label="ALIGNED",
                 prefix_only_rationale="Both explicitly describe the same route relation and anchor.",
                 evidence_verified=True)
        r["review_metadata"].update(prefix_first_review_completed=True, human_content_confirmed=True)
        r["review_metadata"]["prior_exposure"] = {**{k: False for k in rt.EXPOSURES}, "notes": ""}
        return reviews

    def ledger(self, a, b):
        result = rt.adjudication_template(a, b, self.observer_dir)
        result["CASE_A"].update(
            review_status="adjudicated", adjudicator_id="adjudicator_1",
            adjudicated_at="2026-11-09T12:00:00Z", independent_reviews_confirmed=True,
            same_scope_confirmed=True, focal_pair=["giver", "follower"],
            local_question=a["CASE_A"]["local_question"],
            focus_source_ids=deepcopy(a["CASE_A"]["focus_source_ids"]),
            participant_meanings_with_source_quotes=deepcopy(a["CASE_A"]["participant_meanings_with_source_quotes"]),
            label="ALIGNED", blocking_uncertainty=False,
            supported_consequences=deepcopy(a["CASE_A"]["task_outputs"]["supported_consequences"]),
            cluster_id="cluster_demo", cluster_verified=True,
            rationale="The two independently entered readings concern the same route step.")
        return result

    def assert_invalid(self, reviews, contains):
        result = rt.validate_reviews(reviews, self.observer_dir)
        self.assertFalse(result["valid"], result)
        self.assertTrue(any(contains in message for message in result["errors"]), result)

    def test_f7_consequence_sets(self):
        cases = [([1], [1], False, "ALIGNED"),
                 ([1, 1], [1], False, "ALIGNED"),
                 ([1], [2, 3], False, "POTENTIAL_MISMATCH"),
                 ([1, 2], [1, 2], False, "UNRESOLVED"),
                 ([1, 2], [2, 3], False, "UNRESOLVED"),
                 ([], [1], False, "UNRESOLVED"),
                 ([1], [1], True, "UNRESOLVED"),
                 ([{"arg": None}], [{"arg": None}], False, "UNRESOLVED"),
                 ([{"arg": "UNKNOWN"}], [1], False, "UNRESOLVED")]
        for a, b, blocked, expected in cases:
            with self.subTest(a=a, b=b, blocked=blocked):
                self.assertEqual(rt.decision_rule(a, b, blocked), expected)

    def test_migration_preserves_history_and_does_not_certify_ai_wording(self):
        legacy = deepcopy(self.legacy)
        legacy["CASE_A"].update(review_status="reviewed", prefix_first_review_completed=True)
        draft = self.complete()["CASE_A"]
        draft["task_outputs"]["authorship"] = "Assistant wording, not a human judgment."
        result = rt.migrate_reviews(legacy, self.observer_dir, wording={"CASE_A": draft})["CASE_A"]
        self.assertEqual(result["review_status"], "reviewed")
        self.assertTrue(result["review_metadata"]["prefix_first_review_completed"])
        self.assertTrue(result["review_metadata"]["prior_exposure"]["assistant_draft"])
        self.assertFalse(result["review_metadata"]["human_content_confirmed"])
        self.assertIsNone(result["provisional_label"])
        self.assertIsNone(result["include_in_pilot"])

    def test_legacy_readings_get_unknown_support(self):
        legacy = deepcopy(self.legacy)
        legacy["CASE_A"].update(focal_pair=["giver", "follower"], focus_source_ids=[self.rows[0]["utterance_id"]],
                               participant_meanings_with_source_quotes=[{
                                   "participant_id": "giver", "meaning": "Below bridge B.",
                                   "source_quotes": [{"source_id": self.rows[0]["utterance_id"], "quote": self.rows[0]["text"]}]}])
        result = rt.migrate_reviews(legacy, self.observer_dir)["CASE_A"]
        self.assertIsNone(result["participant_meanings_with_source_quotes"][0]["support"])
        self.assertEqual(result["focus_quotes"][0]["quote"], self.rows[0]["text"])

    def test_second_reader_starts_blank_with_unknown_exposure(self):
        r = self.blank("r2")["CASE_A"]
        self.assertEqual(r["reviewer_id"], "r2")
        self.assertEqual(r["review_status"], "unreviewed")
        self.assertIsNone(r["focal_pair"])
        self.assertFalse(r["review_metadata"]["prefix_first_review_completed"])
        self.assertTrue(all(r["review_metadata"]["prior_exposure"][k] is None for k in rt.EXPOSURES))

    def test_unknown_metadata_survives_canonical_roundtrip(self):
        original = self.blank()
        original["CASE_A"]["review_metadata"]["future_events"] = [{"note": "retain this"}]
        self.assertEqual(rt.migrate_reviews(original, self.observer_dir), original)

    def test_complete_record_validates(self):
        result = rt.validate_reviews(self.complete(), self.observer_dir, require_complete=True)
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["completed_reviews"], 1)

    def test_quote_must_be_in_frozen_prefix(self):
        data = self.complete()
        data["CASE_A"]["focus_quotes"][0]["source_id"] = "CASE_A.future.999"
        self.assert_invalid(data, "exact prefix span")

    def test_quote_text_and_speaker_must_match(self):
        for field, value, message in [("quote", "The bridge was adopted.", "exact prefix span"),
                                       ("speaker", "follower", "speaker does not match")]:
            data = self.complete()
            data["CASE_A"]["focus_quotes"][0][field] = value
            self.assert_invalid(data, message)

    def test_substring_focus_is_allowed(self):
        data = self.complete()
        data["CASE_A"]["focus_quotes"][0]["quote"] = "bridge B"
        self.assertTrue(rt.validate_reviews(data, self.observer_dir)["valid"])

    def test_narrator_is_not_a_focal_participant(self):
        data = self.complete()
        data["CASE_A"]["focal_pair"] = ["giver", "Audio"]
        self.assert_invalid(data, "narrator is not a player")

    def test_supported_reading_requires_own_expressed_evidence(self):
        data = self.complete()
        data["CASE_A"]["participant_meanings_with_source_quotes"][1]["source_quotes"] = [
            {"source_id": self.rows[0]["utterance_id"], "quote": self.rows[0]["text"]}]
        self.assert_invalid(data, "participant-owned")

    def test_supported_outcomes_cannot_bypass_reading_support(self):
        data = self.complete()
        data["CASE_A"]["participant_meanings_with_source_quotes"][1]["support"] = "possible"
        data["CASE_A"]["provisional_label"] = None
        self.assert_invalid(data, "nonempty supported consequences")

    def test_label_must_match_consequence_rule(self):
        data = self.complete()
        data["CASE_A"]["task_outputs"]["supported_consequences"]["follower"][0]["relation"] = "above"
        self.assert_invalid(data, "expected POTENTIAL_MISMATCH")

    def test_unrated_records_are_not_agreement(self):
        result = rt.compare_reviews(self.blank(), self.blank("r2"))
        self.assertEqual(result["both_rated"], 0)
        self.assertEqual(result["matching_labels"], 0)
        self.assertEqual(result["records"][0]["state"], "pending_judgments")
        self.assertIsNone(result["records"][0]["label_match"])

    def test_exclusive_creation_preserves_existing_review(self):
        path = self.base / "REVIEWS.json"
        rt.write_new(path, {"saved": True})
        with self.assertRaises(FileExistsError):
            rt.write_new(path, {"saved": False})
        self.assertEqual(rt.load_json(path), {"saved": True})

    def test_pending_adjudication_cannot_export(self):
        a, b = self.complete(), self.complete("r2")
        with self.assertRaisesRegex(ValueError, "No explicit completed adjudications"):
            rt.export_adjudicated(a, b, rt.adjudication_template(a, b, self.observer_dir), self.observer_dir)

    def test_explicit_strict_export_uses_reporter_schema_without_candidate_inference(self):
        a, b = self.complete(), self.complete("r2")
        result = rt.export_adjudicated(a, b, self.ledger(a, b), self.observer_dir)["CASE_A"]
        self.assertEqual(result["reference_condition"], "independent_strict")
        self.assertEqual(result["label"], "ALIGNED")
        self.assertEqual(result["focal_source_ids"], a["CASE_A"]["focus_source_ids"])
        self.assertEqual(result["evidence_review"], {})

    def test_export_binds_exact_observer_content_and_raw_input_file(self):
        a, b = self.complete(), self.complete("r2")
        result = rt.export_adjudicated(a, b, self.ledger(a, b), self.observer_dir)["CASE_A"]
        self.assertEqual(result["observer_hash"], pilot.digest(self.observer))
        self.assertEqual(result["observer_input_sha256"], hashlib.sha256(
            (self.observer_dir / "CASE_A.json").read_bytes()).hexdigest())
        self.assertNotEqual(result["observer_hash"], rt.digest(self.observer),
                            "The run's observer hash uses pilot.digest, not the compact review-record digest.")

    def test_assisted_reference_requires_explicit_condition(self):
        a, b = self.complete(), self.complete("r2")
        a["CASE_A"]["review_metadata"]["prior_exposure"]["assistant_draft"] = True
        ledger = self.ledger(a, b)
        with self.assertRaisesRegex(ValueError, "allow-assisted"):
            rt.export_adjudicated(a, b, ledger, self.observer_dir)
        result = rt.export_adjudicated(a, b, ledger, self.observer_dir, allow_assisted=True)
        self.assertEqual(result["CASE_A"]["reference_condition"], "assisted_development")

    def test_ai_wording_cannot_be_declared_strict_by_clearing_exposure_flags(self):
        a, b = self.complete(), self.complete("r2")
        a["CASE_A"]["review_metadata"]["assistant_wording_fields"] = ["local_question"]
        with self.assertRaisesRegex(ValueError, "allow-assisted"):
            rt.export_adjudicated(a, b, self.ledger(a, b), self.observer_dir)

    def test_later_suggestion_viewing_requires_unchanged_frozen_first_judgment(self):
        record = self.complete()["CASE_A"]
        meta = record["review_metadata"]
        meta["wording_exposure_events"] = [{"before_prefix_first_review": False}]
        self.assertFalse(rt.strict_reference_ready(record))
        meta["first_pass_judgment_snapshot"] = rt.review_judgment_snapshot(record)
        meta["first_pass_judgment_sha256"] = rt.digest(meta["first_pass_judgment_snapshot"])
        self.assertTrue(rt.strict_reference_ready(record))
        record["local_question"] = "A changed task question"
        self.assertFalse(rt.strict_reference_ready(record))

    def test_later_evidence_review_requires_unchanged_frozen_first_judgment(self):
        record = self.complete()["CASE_A"]
        meta = record["review_metadata"]
        meta["later_evidence_review_completed"] = True
        self.assertFalse(rt.strict_reference_ready(record))
        meta["first_pass_judgment_snapshot"] = rt.review_judgment_snapshot(record)
        meta["first_pass_judgment_sha256"] = rt.digest(meta["first_pass_judgment_snapshot"])
        self.assertTrue(rt.strict_reference_ready(record))
        record["prefix_only_rationale"] += " A later outcome changed the conclusion."
        self.assertFalse(rt.strict_reference_ready(record))

    def test_changed_reader_requires_new_adjudication(self):
        a, b = self.complete(), self.complete("r2")
        ledger = self.ledger(a, b)
        a["CASE_A"]["prefix_only_rationale"] += " Additional checked evidence."
        with self.assertRaisesRegex(ValueError, "stale or different"):
            rt.export_adjudicated(a, b, ledger, self.observer_dir)

    def test_unknown_source_cluster_cannot_export(self):
        a, b = self.complete(), self.complete("r2")
        ledger = self.ledger(a, b)
        ledger["CASE_A"]["cluster_verified"] = False
        with self.assertRaisesRegex(ValueError, "source grouping requires review"):
            rt.export_adjudicated(a, b, ledger, self.observer_dir)

    def test_adjudication_cannot_invent_supported_readings_from_sets(self):
        a, b = self.complete(), self.complete("r2")
        ledger = self.ledger(a, b)
        ledger["CASE_A"]["participant_meanings_with_source_quotes"] = []
        with self.assertRaisesRegex(ValueError, "explicit supported participant readings"):
            rt.export_adjudicated(a, b, ledger, self.observer_dir)

    def test_adjudicated_reading_quotes_are_checked(self):
        a, b = self.complete(), self.complete("r2")
        ledger = self.ledger(a, b)
        ledger["CASE_A"]["participant_meanings_with_source_quotes"][1]["source_quotes"][0]["quote"] = "Invented assertion."
        with self.assertRaisesRegex(ValueError, "exact prefix span"):
            rt.export_adjudicated(a, b, ledger, self.observer_dir)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for text in ['{"CASE_A":1,"CASE_A":2}', '{"value": NaN}']:
            path = self.base / "invalid.json"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                rt.load_json(path)

    def test_empty_or_malformed_reviews_fail_cleanly(self):
        self.assertFalse(rt.validate_reviews({}, self.observer_dir)["valid"])
        for field in ["focus_quotes", "participant_meanings_with_source_quotes"]:
            data = self.complete()
            data["CASE_A"][field] = [None]
            self.assertFalse(rt.validate_reviews(data, self.observer_dir)["valid"])


if __name__ == "__main__":
    unittest.main()
