"""Ensure the new editable focus reason and quote representation remain traceable."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import review_tools as rt
import review_key_codec as codec
import tests.test_review_tools as review_fixtures


class ReferenceReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = review_fixtures.ReviewToolsTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_new_reason_and_changed_quote_are_both_reported(self):
        a = self.fixture.complete()
        b = deepcopy(a)
        b['CASE_A']['review_metadata']['focus_selection_reason'] = 'The follower explicitly repeats the route relation.'
        b['CASE_A']['focus_quotes'][0]['quote'] = 'below bridge B'
        result = rt.compare_reviews(codec.to_reference_reviews(a), codec.to_reference_reviews(b))
        differences = result['records'][0]['differences']
        self.assertIn('focus.why_selected', differences)
        self.assertIn('focus_quotes', differences)
        self.assertTrue(result['records'][0]['label_match'])
        self.assertEqual(result['human_adjudications_created'], 0)

    def test_new_reason_cannot_be_added_or_removed_behind_frozen_first_pass(self):
        record = self.fixture.complete()['CASE_A']
        before = rt.review_judgment_snapshot(record)
        self.assertNotIn('focus_selection_reason', before)
        meta = record['review_metadata']
        meta['first_pass_judgment_snapshot'] = deepcopy(before)
        meta['first_pass_judgment_sha256'] = rt.digest(before)
        self.assertTrue(rt.strict_reference_ready(record))
        meta['focus_selection_reason'] = 'A separately recorded focus reason.'
        self.assertFalse(rt.strict_reference_ready(record))
        current = rt.review_judgment_snapshot(record)
        self.assertEqual(current['focus_selection_reason'], meta['focus_selection_reason'])
        meta['first_pass_judgment_snapshot'] = deepcopy(current)
        meta['first_pass_judgment_sha256'] = rt.digest(current)
        self.assertTrue(rt.strict_reference_ready(codec.to_reference_record(record)))
        del meta['focus_selection_reason']
        self.assertFalse(rt.strict_reference_ready(record))

    def test_reference_format_preserves_adjudication_hashes_and_exports(self):
        a, b = self.fixture.complete('r1'), self.fixture.complete('r2')
        ledger = self.fixture.ledger(a, b)
        reference_a, reference_b = codec.to_reference_reviews(a), codec.to_reference_reviews(b)
        self.assertEqual(rt.adjudication_template(reference_a, reference_b, self.fixture.observer_dir),
                         rt.adjudication_template(a, b, self.fixture.observer_dir))
        self.assertEqual(rt.export_adjudicated(reference_a, reference_b, ledger, self.fixture.observer_dir),
                         rt.export_adjudicated(a, b, ledger, self.fixture.observer_dir))

    def test_current_reference_schema_rejects_silent_hypothesis_or_focus_loss(self):
        import jsonschema
        schema = json.loads((Path(__file__).resolve().parents[1] / 'schemas/reviews.schema.json').read_text())
        original = codec.to_reference_reviews(self.fixture.complete())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(original, schema)
        extra_hypothesis = deepcopy(original)
        extra_hypothesis['CASE_A']['subtask_hypotheses'].append({'description': 'A different question.'})
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(extra_hypothesis, schema)
        missing_extra_quotes = deepcopy(original)
        del missing_extra_quotes['CASE_A']['focus']['additional_quotes']
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(missing_extra_quotes, schema)
        conflicting_alias = deepcopy(original)
        conflicting_alias['CASE_A']['Local task question'] = 'An old-key duplicate.'
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(conflicting_alias, schema)


if __name__ == '__main__':
    unittest.main()
