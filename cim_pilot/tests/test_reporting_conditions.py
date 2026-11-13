"""Synthetic reporting checks; these fixtures are not measured pilot results."""
import json
from pathlib import Path
import tempfile
import unittest

from pilot import digest
from report_results import summarize

FIXTURE_OBSERVER_HASH = digest({'fixture': 'identical admitted evidence'})


def saved_fixture(root, sample_id, **overrides):
    prediction = {
        'case_id': sample_id, 'model_id': 'synthetic-test', 'case_role': 'pilot',
        'response_origin': 'external_model', 'is_measured_model_run': True,
        'evidence_tier': 'S', 'prefix_status': 'ALIGNED',
        'observer_hash': FIXTURE_OBSERVER_HASH,
        'candidates': [{'candidate_id': 'c1', 'status': 'ALIGNED',
                        'focus_spans': [{'source_id': 't1', 'quote': 'fixture'}]}],
    }
    prediction.update(overrides)
    case_dir = Path(root) / sample_id
    case_dir.mkdir()
    (case_dir / 'prediction.json').write_text(json.dumps(prediction))
    return {
        'review_status': 'adjudicated', 'label': 'ALIGNED',
        'focal_source_ids': ['t1'], 'cluster_id': 'source-cluster-' + sample_id,
        'evidence_tier': 'S', 'evidence_review': {'c1': True},
        'observer_hash': FIXTURE_OBSERVER_HASH,
    }


class ReportingConditionTests(unittest.TestCase):
    def test_independent_assisted_and_legacy_counts_are_separate(self):
        with tempfile.TemporaryDirectory() as td:
            refs = {sid: saved_fixture(td, sid) for sid in ['a', 'b', 'c']}
            refs['a']['reference_condition'] = 'independent_strict'
            refs['b']['reference_condition'] = 'assisted_development'
            result = summarize(td, refs)
            self.assertEqual(result['counts']['eligible_reviewed_pilot_cases'], 3)
            for condition in ['independent_strict', 'assisted_development', 'unspecified_legacy']:
                self.assertEqual(result['counts_by_reference_condition'][condition]['eligible_reviewed_pilot_cases'], 1)
            self.assertEqual([r['reference_condition'] for r in result['rows']],
                             ['independent_strict', 'assisted_development', 'unspecified_legacy'])
            self.assertIn('source_clusters', result['counts'])
            self.assertNotIn('independent_clusters', result['counts'])

    def test_invalid_adjudicated_label_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            ref = saved_fixture(td, 'a')
            ref['label'] = 'UNCERTAIN'
            with self.assertRaisesRegex(ValueError, 'controlled label'):
                summarize(td, {'a': ref})

    def test_manual_origin_cannot_be_scored_by_measured_flag_alone(self):
        with tempfile.TemporaryDirectory() as td:
            ref = saved_fixture(td, 'a', response_origin='manual_replay')
            result = summarize(td, {'a': ref})
            self.assertFalse(result['rows'][0]['score_eligible'])
            self.assertEqual(result['counts']['eligible_reviewed_pilot_cases'], 0)

    def test_known_non_s_tier_is_visible_and_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            refs = {'a': saved_fixture(td, 'a', evidence_tier='P'),
                    'b': saved_fixture(td, 'b')}
            refs['b']['evidence_tier'] = 'P'
            result = summarize(td, refs)
            self.assertEqual(result['counts']['eligible_reviewed_pilot_cases'], 0)
            self.assertEqual(result['rows'][0]['run_evidence_tier'], 'P')
            self.assertEqual(result['rows'][1]['reference_evidence_tier'], 'P')

    def test_unknown_reference_condition_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            ref = saved_fixture(td, 'a')
            ref['reference_condition'] = 'blind'
            with self.assertRaisesRegex(ValueError, 'reference_condition'):
                summarize(td, {'a': ref})

    def test_changed_context_hash_prevents_scoring_same_case_and_focus(self):
        with tempfile.TemporaryDirectory() as td:
            ref = saved_fixture(td, 'a')
            ref['observer_hash'] = digest({'fixture': 'changed admitted context'})
            result = summarize(td, {'a': ref})
            self.assertEqual(result['rows'][0]['input_binding_status'], 'mismatch')
            self.assertFalse(result['rows'][0]['score_eligible'])
            self.assertEqual(result['counts']['correct_labels'], 0)
            self.assertEqual(result['input_binding_status_counts'], {'mismatch': 1})

    def test_legacy_missing_hashes_are_explicitly_unverified_and_ineligible(self):
        with tempfile.TemporaryDirectory() as td:
            refs = {'a': saved_fixture(td, 'a'), 'b': saved_fixture(td, 'b', observer_hash=None)}
            del refs['a']['observer_hash']
            result = summarize(td, refs)
            self.assertEqual(result['counts']['eligible_reviewed_pilot_cases'], 0)
            self.assertEqual(result['input_binding_status_counts'],
                             {'missing_reference_hash': 1, 'missing_run_hash': 1})
            self.assertEqual(result['rows'][0]['reference_condition'], 'unspecified_legacy')

    def test_equal_but_invalid_hash_strings_do_not_establish_binding(self):
        with tempfile.TemporaryDirectory() as td:
            ref = saved_fixture(td, 'a', observer_hash='placeholder')
            ref['observer_hash'] = 'placeholder'
            result = summarize(td, {'a': ref})
            self.assertEqual(result['rows'][0]['input_binding_status'], 'invalid_reference_hash')
            self.assertFalse(result['rows'][0]['score_eligible'])


if __name__ == '__main__':
    unittest.main()
