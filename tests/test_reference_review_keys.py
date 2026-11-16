"""Lossless reference-shaped review conversion and ambiguity boundaries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from review_key_codec import (MAPS, REFERENCE_FORMAT_ID, REFERENCE_FIELD_PATHS,
                              ReviewKeyCollisionError, to_human_record,
                              to_human_reviews, to_reference_record,
                              to_reference_reviews, to_technical_record,
                              to_technical_reviews)

ROOT = Path(__file__).resolve().parents[1]


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class ReferenceReviewKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.technical = to_technical_reviews(load("REVIEWS.json"))
        cls.case_id = next(iter(cls.technical))

    def record(self):
        return deepcopy(self.technical[self.case_id])

    def test_all_20_main_blank_and_wording_records_round_trip(self):
        for filename in ["REVIEWS.json", "reviews/reader_2/REVIEWS.json",
                         "wording/REVIEWS_A.json", "wording/REVIEWS_B.json"]:
            with self.subTest(filename=filename):
                source = load(filename)
                canonical = to_technical_reviews(source)
                frozen = deepcopy(canonical)
                converted = to_reference_reviews(source)
                self.assertEqual(len(converted), 20)
                self.assertEqual(to_technical_reviews(converted), canonical)
                self.assertEqual(to_human_reviews(converted), to_human_reviews(canonical))
                self.assertEqual(canonical, frozen)
                self.assertEqual(canonical_sha(to_technical_reviews(converted)), canonical_sha(canonical))
                for record in converted.values():
                    self.assertIsNone(record["focus"]["why_selected"])
                    self.assertEqual(len(record["subtask_hypotheses"]), 1)
                    self.assertEqual(set(record["subtask_hypotheses"][0]), {"description"})

    def test_structure_keeps_inner_readable_keys_and_controlled_values(self):
        original = self.record()
        converted = to_reference_record(original)
        self.assertEqual(REFERENCE_FORMAT_ID, "CIM_REFERENCE_KEYS_V1")
        self.assertEqual(converted["participant_interpretations"],
                         to_human_record(original)[MAPS["review"]["participant_meanings_with_source_quotes"]])
        self.assertEqual(converted["consequence_analysis"],
                         to_human_record(original)[MAPS["review"]["task_outputs"]])
        self.assertEqual(converted["Review judgment"], original["provisional_label"])
        self.assertEqual(converted["rationale"], original["prefix_only_rationale"])
        self.assertEqual(converted["selection_reason"], original["inclusion_or_exclusion_reason"])

    def test_primary_additional_quotes_and_original_selected_order(self):
        record = self.record()
        record["focus_source_ids"] = ["t2", "t1", "t2"]
        record["focus_quotes"] = [
            {"source_id": "t1", "quote": "first", "speaker": "A", "confidence_note": {"rank": 2},
             "utterance_id": "opaque old quote field", "why_selected": "opaque quote attribute"},
            {"source_id": "t2", "quote": "second", "speaker": "B", "offsets": [1, 3]},
            {"source_id": "t1", "quote": "first again", "opaque": False},
        ]
        converted = to_reference_record(record)
        focus = converted["focus"]
        self.assertEqual(focus["utterance_id"], "t1")
        self.assertEqual(focus["selected_utterance_ids"], ["t2", "t1", "t2"])
        self.assertEqual(focus["quote_metadata"]["why_selected"], "opaque quote attribute")
        self.assertEqual(focus["additional_quotes"][0],
                         {"utterance_id": "t2", "quote": "second", "speaker": "B", "offsets": [1, 3]})
        self.assertEqual(to_technical_record(converted), record)

    def test_blank_focus_and_null_question_do_not_create_human_content(self):
        record = next(iter(to_technical_reviews(load("reviews/reader_2/REVIEWS.json")).values()))
        converted = to_reference_record(record)
        self.assertEqual(converted["focus"], {"utterance_id": None, "quote": None,
                                             "why_selected": None, "additional_quotes": [],
                                             "selected_utterance_ids": []})
        self.assertEqual(converted["subtask_hypotheses"], [{"description": None}])
        self.assertEqual(to_technical_record(converted), record)
        self.assertNotIn("focus_selection_reason", to_technical_record(converted)["review_metadata"])

    def test_opaque_unknown_fields_and_strings_are_unchanged(self):
        record = self.record()
        record["custom_review_note"] = {"rationale": "local_question is data here", "focus": {"other": 1}}
        record["review_metadata"]["history"] = {"subtask_hypotheses": [{"not_description": "opaque"}]}
        record["task_outputs"]["supported_consequences"] = {"rationale": [{"focus": "literal outcome"}]}
        self.assertEqual(to_technical_record(to_reference_record(record)), record)

    def test_old_and_new_alias_collisions_are_rejected_even_when_equal(self):
        for technical, reference in [("local_question", "subtask_hypotheses"),
                                     ("participant_meanings_with_source_quotes", "participant_interpretations"),
                                     ("task_outputs", "consequence_analysis"),
                                     ("prefix_only_rationale", "rationale"),
                                     ("inclusion_or_exclusion_reason", "selection_reason")]:
            for alias in [technical, MAPS["review"][technical]]:
                with self.subTest(technical=technical, alias=alias):
                    reference_record = to_reference_record(self.record())
                    reference_record[alias] = self.record()[technical]
                    with self.assertRaises(ReviewKeyCollisionError):
                        to_technical_record(reference_record)
        for alias in ["focus_source_ids", "focus_quotes", "Selected dialogue turns", "Selected expressions"]:
            reference_record = to_reference_record(self.record())
            reference_record[alias] = []
            with self.assertRaises(ReviewKeyCollisionError):
                to_human_record(reference_record)

    def test_only_one_description_hypothesis_is_supported(self):
        for hypotheses in [[], [{"description": "a"}, {"description": "b"}],
                           {"description": "a"}, [None], [{"description": "a", "confidence": 1}],
                           [{"description": 13}]]:
            with self.subTest(hypotheses=hypotheses):
                with self.assertRaises(ValueError):
                    to_technical_record({"subtask_hypotheses": hypotheses})
        self.assertEqual(to_technical_record({"subtask_hypotheses": [{"description": None}]}),
                         {"local_question": None})
        self.assertNotIn("subtask_hypotheses", to_reference_record({"reviewer_id": "r1"}))

    def test_partial_legacy_focus_rejected_only_for_reference_export(self):
        for partial in [{"focus_source_ids": []}, {"focus_quotes": []}]:
            self.assertEqual(to_technical_record(to_human_record(partial)), partial)
            with self.assertRaises(ValueError):
                to_reference_record(partial)

    def test_malformed_reference_focus_is_not_repaired(self):
        valid = to_reference_record(self.record())["focus"]
        invalid = [None, [], {}, {**valid, "unknown": 1},
                   {**valid, "selected_utterance_ids": "t1"},
                   {**valid, "additional_quotes": None},
                   {**valid, "utterance_id": None, "quote": "text"},
                   {**valid, "why_selected": False},
                   {"utterance_id": None, "quote": None, "speaker": "A",
                    "selected_utterance_ids": [], "additional_quotes": []},
                   {"utterance_id": None, "quote": None, "quote_metadata": {},
                    "selected_utterance_ids": [], "additional_quotes": []},
                   {"utterance_id": None, "quote": None, "selected_utterance_ids": [],
                    "additional_quotes": [{"utterance_id": "t1", "quote": "text"}]}]
        for focus in invalid:
            with self.subTest(focus=focus):
                with self.assertRaises(ValueError):
                    to_technical_record({"focus": focus})

    def test_primary_reserved_metadata_and_additional_aliases_rejected(self):
        for key in ["source_id", "speaker", "quote", "Source turn", "Speaker", "Exact expression"]:
            with self.subTest(key=key):
                record = to_reference_record(self.record())
                record["focus"]["quote_metadata"] = {key: "duplicate"}
                with self.assertRaises(ReviewKeyCollisionError):
                    to_technical_record(record)
        for key in ["source_id", "Source turn", "Speaker", "Exact expression"]:
            with self.subTest(key=key):
                record = to_reference_record(self.record())
                record["focus"]["additional_quotes"] = [{"utterance_id": "t2", "quote": "text", key: "duplicate"}]
                with self.assertRaises(ReviewKeyCollisionError):
                    to_technical_record(record)

    def test_field_reference_lists_translate_paths_without_touching_data(self):
        record = self.record()
        fields = list(REFERENCE_FIELD_PATHS)
        record["review_metadata"]["assistant_wording_fields"] = fields
        record["review_metadata"]["wording_exposure_events"] = [{"fields": fields, "action": "rationale"}]
        reference = to_reference_record(record)
        meta = reference["Reviewer and exposure"]
        expected = list(REFERENCE_FIELD_PATHS.values())
        self.assertEqual(meta["Draft wording fields"], expected)
        self.assertEqual(meta["Wording consultation history"][0]["Fields"], expected)
        self.assertEqual(meta["Wording consultation history"][0]["Action"], "rationale")
        self.assertEqual(to_technical_record(reference), record)
        meta["Draft wording fields"] = ["local_question", "subtask_hypotheses[0].description"]
        with self.assertRaises(ReviewKeyCollisionError):
            to_technical_record(reference)

    def test_first_pass_snapshot_and_hash_round_trip(self):
        record = self.record()
        snapshot = {key: deepcopy(record[key]) for key in [
            "reviewer_id", "focal_pair", "local_question", "focus_source_ids", "focus_quotes",
            "participant_meanings_with_source_quotes", "task_outputs", "blocking_uncertainty",
            "provisional_label", "prefix_only_rationale", "evidence_verified"]}
        record["review_metadata"]["first_pass_judgment_snapshot"] = snapshot
        record["review_metadata"]["first_pass_judgment_sha256"] = canonical_sha(snapshot)
        converted = to_reference_record(record)
        saved = converted["Reviewer and exposure"]["Saved first judgment"]
        self.assertIn("subtask_hypotheses", saved)
        self.assertIn("focus", saved)
        restored = to_technical_record(converted)
        self.assertEqual(restored, record)
        self.assertEqual(canonical_sha(restored["review_metadata"]["first_pass_judgment_snapshot"]),
                         restored["review_metadata"]["first_pass_judgment_sha256"])
        self.assertEqual(to_technical_record(to_reference_record(snapshot)), snapshot)

    def test_actual_focus_reason_round_trip_in_full_review_and_snapshot(self):
        record = self.record()
        record["review_metadata"]["focus_selection_reason"] = "The expression is the point being compared."
        snapshot = {key: deepcopy(record[key]) for key in ["reviewer_id", "local_question", "focus_source_ids", "focus_quotes"]}
        snapshot["focus_selection_reason"] = record["review_metadata"]["focus_selection_reason"]
        record["review_metadata"]["first_pass_judgment_snapshot"] = snapshot
        record["review_metadata"]["first_pass_judgment_sha256"] = canonical_sha(snapshot)
        reference = to_reference_record(record)
        self.assertEqual(reference["focus"]["why_selected"], snapshot["focus_selection_reason"])
        self.assertNotIn("focus_selection_reason", reference["Reviewer and exposure"])
        self.assertEqual(reference["Reviewer and exposure"]["Saved first judgment"]["focus"]["why_selected"],
                         snapshot["focus_selection_reason"])
        self.assertEqual(to_technical_record(reference), record)
        self.assertEqual(to_technical_record(to_reference_record(snapshot)), snapshot)
        self.assertEqual(to_human_record(reference), to_human_record(record))

    def test_null_or_absent_why_does_not_add_metadata_empty_text_is_preserved(self):
        record = self.record()
        reference = to_reference_record(record)
        self.assertNotIn("focus_selection_reason", to_technical_record(reference)["review_metadata"])
        del reference["focus"]["why_selected"]
        self.assertEqual(to_technical_record(reference), record)
        reference["focus"]["why_selected"] = ""
        expected = deepcopy(record)
        expected["review_metadata"]["focus_selection_reason"] = ""
        self.assertEqual(to_technical_record(reference), expected)
        self.assertEqual(to_reference_record(expected)["focus"]["why_selected"], "")
        record["review_metadata"]["focus_selection_reason"] = None
        with self.assertRaises(ValueError):
            to_reference_record(record)

    def test_double_reason_declarations_rejected_even_if_equal_or_null(self):
        for reason in [None, "same"]:
            reference = to_reference_record(self.record())
            reference["focus"]["why_selected"] = reason
            reference["Reviewer and exposure"]["focus_selection_reason"] = reason
            with self.assertRaises(ReviewKeyCollisionError):
                to_technical_record(reference)
        snapshot = {"focus_source_ids": [], "focus_quotes": [], "focus_selection_reason": "same"}
        ref = to_reference_record(snapshot)
        ref["focus_selection_reason"] = "same"
        with self.assertRaises(ReviewKeyCollisionError):
            to_technical_record(ref)

    def test_conversion_is_idempotent_and_never_mutates_input(self):
        record = self.record()
        before = deepcopy(record)
        ref = to_reference_record(record)
        ref_before = deepcopy(ref)
        self.assertEqual(to_reference_record(ref), ref)
        self.assertEqual(to_technical_record(to_technical_record(ref)), record)
        self.assertEqual(record, before)
        self.assertEqual(ref, ref_before)


if __name__ == "__main__":
    unittest.main()
