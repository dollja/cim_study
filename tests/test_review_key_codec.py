"""Review-key conversion must preserve evidence, decisions and canonical hashes."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest

import review_key_codec as codec
import review_tools as rt
import tests.test_review_tools as review_fixtures


class ReviewKeyCodecTests(unittest.TestCase):
    def setUp(self):
        self.fixture = review_fixtures.ReviewToolsTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def cli(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = rt.main(args)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_original_form_quotes_have_distinct_contextual_keys(self):
        original = self.fixture.complete()
        human = codec.to_human_reviews(original)
        record = human['CASE_A']
        focus = record['Selected expressions'][0]
        quote = record['Each participant’s reading'][0]['Evidence quotes'][0]
        self.assertEqual(set(focus), {'Source turn', 'Speaker', 'Exact expression'})
        self.assertEqual(set(quote), {'Evidence source', 'Exact evidence'})
        self.assertEqual(focus['Exact expression'], original['CASE_A']['focus_quotes'][0]['quote'])
        self.assertEqual(codec.to_technical_reviews(human), original)
        self.assertEqual(codec.to_human_reviews(human), human)
        self.assertEqual(codec.to_technical_reviews(original), original)

    def test_all_declared_contexts_round_trip_without_touching_opaque_data(self):
        record = self.fixture.complete()['CASE_A']
        record['unknown_extra'] = {'review_status': 1, 'Review status': 2}
        meta = record['review_metadata']
        meta['unknown_history'] = {'reviewer_id': 'literal', 'Reviewer': 'also literal'}
        meta['assistant_wording_fields'] = ['local_question', 'task_outputs', 'unknown_future_field']
        meta['first_pass_judgment_snapshot'] = rt.review_judgment_snapshot(record)
        meta['first_pass_judgment_sha256'] = rt.digest(meta['first_pass_judgment_snapshot'])
        meta['first_pass_recorded_at_utc'] = '2026-11-13T12:00:00Z'
        meta['reference_condition'] = 'assisted_development'
        meta['provenance_record'] = 'review_provenance/example.json'
        meta['wording_exposure_events'] = [{
            'at_utc': '2026-11-13T12:01:00Z', 'source_filename': 'example.json',
            'action': 'view', 'before_prefix_first_review': False,
            'fields': ['participant_meanings_with_source_quotes', 'prefix_only_rationale'],
            'future_event_detail': {'quote': 'quote', 'review_status': 'literal'}}]
        record['participant_meanings_with_source_quotes'][0]['support_note'] = 'Quoted word: reviewer_id.'
        outputs = record['task_outputs']
        for key in codec.MAPS['task_outputs']:
            outputs.setdefault(key, 'Literal task prose: local_question.')
        outputs['evidence_tier'] = 'S'
        outputs['participant_outputs'] = {'Reviewer': {'source_id': 'literal ID', 'quote': 'quote'}}
        outputs['supported_consequences'] = {
            'Review status': [{'review_status': 'literal payload', 'Exact evidence': None}],
            'reviewer_id': [['Route', 'step1', 'below', None]]}
        original = deepcopy(record)
        human = codec.to_human_record(record)
        self.assertEqual(codec.to_technical_record(human), original)
        self.assertEqual(record, original, 'The input must not be mutated.')
        self.assertEqual(human['Task consequences']['Consequences by participant'], outputs['participant_outputs'])
        self.assertEqual(human['Task consequences']['Supported consequences JSON'], outputs['supported_consequences'])
        self.assertEqual(human['unknown_extra'], original['unknown_extra'])
        human_meta = human['Reviewer and exposure']
        self.assertEqual(human_meta['unknown_history'], meta['unknown_history'])
        self.assertEqual(human_meta['Draft wording fields'],
                         ['Local task question', 'Task consequences', 'unknown_future_field'])
        self.assertEqual(human_meta['Wording consultation history'][0]['Fields'],
                         ['Each participant’s reading', 'Why this judgment? Prefix evidence only'])
        # Every context's known keys occurs at a mapped structural location.
        self.assertTrue(set(codec.MAPS['metadata'].values()) <= set(human_meta))
        self.assertTrue(set(codec.MAPS['task_outputs'].values()) <= set(human['Task consequences']))

    def test_malformed_shapes_and_identical_field_references_are_not_repaired(self):
        original = {'review_metadata': {'assistant_wording_fields': ['local_question', 'local_question']},
                    'focus_quotes': {'source_id': 'not an array'},
                    'participant_meanings_with_source_quotes': [None, 0, 'not an object'],
                    'task_outputs': ['not an object'], 'blocking_uncertainty': 'false'}
        human = codec.to_human_record(original)
        self.assertEqual(codec.to_technical_record(human), original)
        self.assertEqual(human['Could uncertainty change the conclusion?'], 'false')
        self.assertEqual(codec.to_human_reviews([None, False]), [None, False])

    def test_alias_collisions_rejected_even_when_values_equal(self):
        cases = [
            {'reviewer_id': 'r1', 'Reviewer': 'r1'},
            {'review_metadata': {'prior_exposure': {'assistant_draft': True, 'Assistant drafts': True}}},
            {'focus_quotes': [{'source_id': 'row1', 'Source turn': 'row1', 'quote': 'same'}]},
            {'review_metadata': {'first_pass_judgment_snapshot': {'local_question': 'same', 'Local task question': 'same'}}},
            {'review_metadata': {'assistant_wording_fields': ['local_question', 'Local task question']}},
        ]
        for record in cases:
            for convert in [codec.to_human_record, codec.to_technical_record]:
                with self.subTest(record=record, convert=convert.__name__):
                    with self.assertRaises(codec.ReviewKeyCollisionError):
                        convert(record)

    def test_noncolliding_mixed_input_is_canonicalized(self):
        mixed = {'Reviewer': 'r1', 'local_question': 'Same question?',
                 'Reviewer and exposure': {'prior_exposure': {'Assistant drafts': True}}}
        self.assertEqual(codec.to_technical_record(mixed), {
            'reviewer_id': 'r1', 'local_question': 'Same question?',
            'review_metadata': {'prior_exposure': {'assistant_draft': True}}})

    def test_first_pass_snapshot_and_record_hashes_survive_serialization(self):
        record = self.fixture.complete()['CASE_A']
        meta = record['review_metadata']
        meta['wording_exposure_events'] = [{'before_prefix_first_review': False, 'fields': ['local_question']}]
        meta['first_pass_judgment_snapshot'] = rt.review_judgment_snapshot(record)
        meta['first_pass_judgment_sha256'] = rt.digest(meta['first_pass_judgment_snapshot'])
        human = json.loads(json.dumps(codec.to_human_record(record), ensure_ascii=False))
        decoded = codec.to_technical_record(human)
        self.assertEqual(rt.digest(decoded), rt.digest(record))
        self.assertEqual(rt.digest(decoded['review_metadata']['first_pass_judgment_snapshot']),
                         meta['first_pass_judgment_sha256'])
        self.assertEqual(rt.review_judgment_snapshot(human), rt.review_judgment_snapshot(record))
        self.assertTrue(rt.strict_reference_ready(human))
        human['Local task question'] += ' Changed after first pass.'
        self.assertFalse(rt.strict_reference_ready(human))

    def test_validation_comparison_migration_and_adjudication_accept_both_formats(self):
        a, b = self.fixture.complete(), self.fixture.complete('r2')
        ah, bh = codec.to_human_reviews(a), codec.to_human_reviews(b)
        obs = self.fixture.observer_dir
        self.assertEqual(rt.validate_reviews(ah, obs, True), rt.validate_reviews(a, obs, True))
        self.assertEqual(rt.compare_reviews(ah, bh), rt.compare_reviews(a, b))
        self.assertEqual(rt.compare_reviews(ah, b), rt.compare_reviews(a, b))
        self.assertEqual(rt.migrate_reviews(ah, obs), a)
        self.assertEqual(rt.adjudication_template(ah, bh, obs), rt.adjudication_template(a, b, obs))
        ledger = self.fixture.ledger(a, b)
        self.assertEqual(rt.export_adjudicated(ah, bh, ledger, obs), rt.export_adjudicated(a, b, ledger, obs))
        self.assertIn('review_status', ledger['CASE_A'], 'Ledger keys remain technical.')

    def test_validation_reports_alias_collision_without_choosing_a_value(self):
        data = codec.to_human_reviews(self.fixture.complete())
        data['CASE_A']['provisional_label'] = data['CASE_A']['Review judgment']
        result = rt.validate_reviews(data, self.fixture.observer_dir)
        self.assertFalse(result['valid'])
        self.assertTrue(any('Conflicting review-key aliases' in error for error in result['errors']))

    def test_key_only_cli_preserves_invalid_mt10_style_judgment_and_true_exposure(self):
        data = self.fixture.complete()
        record = data['CASE_A']
        for values in record['task_outputs']['supported_consequences'].values():
            values[0]['anchor'] = None
        record['review_metadata']['prior_exposure']['assistant_draft'] = True
        source, output = self.fixture.base/'source.json', self.fixture.base/'human.json'
        rt.write_new(source, data)
        status, stdout, stderr = self.cli(['convert-keys', str(source), '--out', str(output)])
        self.assertEqual(status, 0, stderr)
        self.assertFalse(json.loads(stdout)['semantic_validation_performed'])
        human = rt.load_json(output)
        self.assertEqual(codec.to_technical_reviews(human), data)
        self.assertIs(human['CASE_A']['Could uncertainty change the conclusion?'], False)
        self.assertEqual(human['CASE_A']['Review judgment'], 'ALIGNED')
        self.assertIs(human['CASE_A']['Reviewer and exposure']['What had you seen before your first judgment?']['Assistant drafts'], True)
        result = rt.validate_reviews(human, self.fixture.observer_dir)
        self.assertFalse(result['valid'])
        self.assertTrue(any('expected UNRESOLVED' in error for error in result['errors']))
        status, _, _ = self.cli(['convert-keys', str(source), '--out', str(output)])
        self.assertEqual(status, 2, 'Existing reviews cannot be overwritten.')

    def test_cli_migrate_defaults_reference_and_supports_both_earlier_formats(self):
        data = self.fixture.complete()
        source = self.fixture.base/'input.json'
        rt.write_new(source, codec.to_human_reviews(data))
        for convention in ['reference', 'human', 'technical']:
            destination = self.fixture.base/(convention + '.json')
            args = ['migrate', str(source), '--observer-dir', str(self.fixture.observer_dir),
                    '--out', str(destination)]
            if convention != 'reference':
                args += ['--output-keys', convention]
            status, _, stderr = self.cli(args)
            self.assertEqual(status, 0, stderr)
            expected = (codec.to_reference_reviews(data) if convention == 'reference' else
                        codec.to_human_reviews(data) if convention == 'human' else data)
            self.assertEqual(rt.load_json(destination), expected)

    def test_human_and_preserved_technical_schemas(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('jsonschema is optional; runtime CLI validation has no dependency on it.')
        base = Path(__file__).resolve().parents[1]/'schemas'
        human_schema = json.loads((base/'reviews_form_labels.schema.json').read_text())
        technical_schema = json.loads((base/'reviews_technical.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(human_schema)
        jsonschema.Draft202012Validator.check_schema(technical_schema)
        data = self.fixture.complete()
        jsonschema.validate(codec.to_human_reviews(data), human_schema)
        jsonschema.validate(data, technical_schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(data, human_schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(codec.to_human_reviews(data), technical_schema)


if __name__ == '__main__':
    unittest.main()
