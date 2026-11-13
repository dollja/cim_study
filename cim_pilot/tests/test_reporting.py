import json
import tempfile
import unittest
from pathlib import Path
from pilot import digest
from report_results import summarize

FIXTURE_OBSERVER_HASH = digest({"fixture": "identical admitted evidence"})

class ReportingTests(unittest.TestCase):
    def test_exposed_teaching_runs_not_scored_as_pilot(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"r";p.mkdir()
            (p/"prediction.json").write_text(json.dumps({
              "case_id":"demo","model_id":"fixture","case_role":"teaching",
              "response_origin":"manual_replay","is_measured_model_run":False,
              "prefix_status":"ALIGNED","candidates":[]}))
            result=summarize(td,{})
            self.assertEqual(result["counts"]["runs"],1)
            self.assertEqual(result["counts"]["eligible_reviewed_pilot_cases"],0)

    def test_unresolved_reference_separate_from_negative(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"r";p.mkdir()
            (p/"prediction.json").write_text(json.dumps({
              "case_id":"a","model_id":"model","case_role":"pilot",
              "response_origin":"external_model","is_measured_model_run":True,
              "observer_hash":FIXTURE_OBSERVER_HASH,
              "prefix_status":"POTENTIAL_MISMATCH",
              "candidates":[{"candidate_id":"c1","status":"POTENTIAL_MISMATCH",
                             "focus_spans":[{"source_id":"t1","quote":"x"}]}]}))
            ref={"a":{"review_status":"adjudicated","label":"UNRESOLVED",
                       "observer_hash":FIXTURE_OBSERVER_HASH,
                       "focal_source_ids":["t1"],"cluster_id":"m9"}}
            c=summarize(td,ref)["counts"]
            self.assertEqual(c["aligned_reference_cases"],0)
            self.assertEqual(c["warnings_on_unresolved_report_separately"],1)

    def test_label_match_needs_independent_evidence_review(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"r";p.mkdir()
            (p/"prediction.json").write_text(json.dumps({
              "case_id":"a","model_id":"model","case_role":"pilot",
              "response_origin":"external_model","is_measured_model_run":True,
              "observer_hash":FIXTURE_OBSERVER_HASH,
              "prefix_status":"ALIGNED","candidates":[{"candidate_id":"c1","status":"ALIGNED",
                "focus_spans":[{"source_id":"t1","quote":"x"}]}]}))
            ref={"a":{"review_status":"adjudicated","label":"ALIGNED",
                       "observer_hash":FIXTURE_OBSERVER_HASH,
                       "focal_source_ids":["t1"],"cluster_id":"m9"}}
            c=summarize(td,ref)["counts"]
            self.assertEqual(c["correct_labels"],1)
            self.assertEqual(c["correct_with_reviewed_evidence"],0)

if __name__=="__main__":unittest.main()
