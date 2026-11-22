"""Controls for the integrated slide-9 rule and strict evidence boundaries.

These are software fixtures, not observations or model-performance results.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pilot import advance, alternatives_block, check_view, compare, evaluate_hypothesis, task
from tests.test_pilot import fixture


class IntegratedRuleTests(unittest.TestCase):
    def test_f7_consequence_sets_not_wording_or_any_overlap(self):
        cases = [
            ({('date', 'Sep15')}, {('date', 'Sep15')}, False, 'ALIGNED'),
            ({('date', 'Sep15'), ('date', 'Sep20')}, {('date', 'Nov15')}, False, 'POTENTIAL_MISMATCH'),
            ({('a',), ('b',)}, {('b',), ('c',)}, False, 'UNRESOLVED'),
            ({('a',), ('b',)}, {('a',), ('b',)}, False, 'UNRESOLVED'),
            (set(), {('a',)}, False, 'UNRESOLVED'),
            ({None}, {('a',)}, False, 'UNRESOLVED'),
            ({('a',)}, {('b',)}, True, 'UNRESOLVED'),
            ({('a',)}, {('a',)}, True, 'UNRESOLVED'),
        ]
        for ga, gb, blocker, expected in cases:
            with self.subTest(ga=ga, gb=gb, blocker=blocker):
                self.assertEqual(compare(ga, gb, blocker), expected)

    def test_known_q_outcome_already_in_g_does_not_block(self):
        g = {('route', 'upper'), ('route', 'lower')}
        q = {('route', 'upper')}
        self.assertFalse(alternatives_block(g, q))
        self.assertEqual(compare(g, {('route', 'third')}, alternatives_block(g, q)),
                         'POTENTIAL_MISMATCH')
        self.assertTrue(alternatives_block(g, {None}))
        self.assertTrue(alternatives_block(g, {('route', 'third')}))

    def test_same_output_q_is_nonblocking_in_full_evaluation(self):
        v, c, h, readings, records, checks = fixture()
        for source in v['context_sources']:
            for entity in source['adapter']['entities']:
                entity['class_id'] = 'shared'
        for reading in readings['readings']:
            reading['arguments']['anchor_class'] = 'shared'
        records['F']['records'][0]['judgment'] = 'undetermined'
        checks['F']['reading_reviews'][0]['judgment'] = 'undetermined'
        result = evaluate_hypothesis(v, c, h, readings, records, checks)
        self.assertEqual(result['participants']['F']['Q'], ['upper'])
        self.assertFalse(result['participants']['F']['blocking_alternatives'])
        self.assertEqual(result['status'], 'ALIGNED')

    def test_wrongly_typed_reading_arguments_give_unknown_consequence_not_a_crash(self):
        v = {'participants': [{'participant_id': 'A'}, {'participant_id': 'B'}],
             'context_sources': [{'source_id': 'rules', 'text': 'r', 'accessible_to_participants': ['A', 'B'],
                                  'adapter': {'kind': 'game_rules', 'review_status': 'verified',
                                              'roles': ['Robber', 'Seer']}}]}
        good = {'event_id': 'e1', 'mode': 'reported', 'role': 'Robber', 'holder': 'A',
                'phase': 'night', 'premise_branch': 'as stated'}
        holder = {'subtask': 'holder', 'event_id': 'e1'}
        self.assertEqual(task(v, 'A', holder, {'arguments': good}),
                         ('Holder', 'e1', 'Robber', 'A', 'night', 'as stated'))
        bad = [dict(good, premise_branch=['quote one', 'quote two']), dict(good, holder={'participant_id': 'A'}),
               dict(good, role=['Robber']), dict(good, phase={'name': 'night'}),
               dict(good, mode='swap', order_resolved=True, no_later_movement=True, initial_state=['A']),
               dict(good, mode='swap', order_resolved=True, no_later_movement=True, initial_state={'A': 'Robber'},
                    moves=[{'operation': 'swap', 'a': ['A'], 'b': 'B'}])]
        for arguments in bad:
            with self.subTest(arguments=arguments):
                self.assertIsNone(task(v, 'A', holder, {'arguments': arguments}))
        target = {'subtask': 'target', 'event_id': 'e1'}
        self.assertIsNone(task(v, 'A', target, {'arguments': {'event_id': 'e1', 'target': ['B'], 'act': 'vote'}}))
        route = {'subtask': 'route', 'event_id': 'e1'}
        for arguments in ({'event_id': 'e1', 'anchor_ids': ['x'], 'relation': 'above'},
                          {'event_id': 'e1', 'anchor_ids': {'A': ['x']}, 'relation': ['above']}):
            self.assertIsNone(task(v, 'A', route, {'arguments': arguments}))

    def test_final_ack_does_not_erase_prior_expressed_grounding(self):
        v, c, h, readings, records, checks = fixture()
        v['dialogue_prefix'].append({'utterance_id': 't3', 'speaker': 'F', 'text': 'Okay.'})
        # The existing F support path stays rooted in F's explicit t2 description.
        result = evaluate_hypothesis(v, c, h, readings, records, checks)
        self.assertEqual(result['status'], 'POTENTIAL_MISMATCH')
        self.assertEqual(result['participants']['F']['X'], ['lower'])

    def test_map_plus_ungrounded_ack_cannot_supply_missing_support(self):
        v, c, h, readings, records, checks = fixture()
        v['dialogue_prefix'][1]['text'] = 'Okay.'
        path = records['F']['records'][1]['paths'][0]
        path['root'] = {'source_id': 't2', 'quote': 'Okay.'}
        path['links'] = [{'relation': 'MAP_FACT', 'source_id': 'mapF', 'quote': 'lower van'}]
        checks['F']['path_checks'][0]['verdict'] = 'undetermined'
        result = evaluate_hypothesis(v, c, h, readings, records, checks)
        self.assertEqual(result['status'], 'UNRESOLVED')
        self.assertEqual(result['participants']['F']['X'], [])

    def test_nested_review_metadata_is_not_an_observer_field(self):
        for location in ['participant', 'source', 'adapter', 'entity']:
            v, *_ = fixture()
            targets = {'participant': v['participants'][0],
                       'source': v['context_sources'][0],
                       'adapter': v['context_sources'][0]['adapter'],
                       'entity': v['context_sources'][0]['adapter']['entities'][0]}
            targets[location]['manual_annotation'] = {'label': 'ALIGNED'}
            with self.subTest(location=location), self.assertRaises(ValueError):
                check_view(v)

    def test_hidden_game_roles_are_not_participant_metadata(self):
        v, *_ = fixture()
        v['participants'][0]['known_role'] = 'Werewolf'
        v['context_sources'] = [{'source_id': 'rules', 'text': 'Public rule.',
            'accessible_to_participants': ['G', 'F'],
            'adapter': {'kind': 'game_rules', 'review_status': 'verified',
                        'roles': ['Werewolf', 'Villager']}}]
        with self.assertRaisesRegex(ValueError, 'participant truth'):
            check_view(v)

    def test_invalid_support_code_is_a_processing_contract_error(self):
        v, c, h, readings, records, checks = fixture()
        checks['F']['path_checks'][0]['verdict'] = 'SUPPORTED'
        with self.assertRaisesRegex(ValueError, 'path-check verdict'):
            evaluate_hypothesis(v, c, h, readings, records, checks)

    def test_nonobject_duplicate_key_and_nonjson_responses_are_failures(self):
        for text in ['[]', 'null', '{"candidates":[],"overflow":false,"overflow":true}',
                     '{"candidates":[],"overflow":NaN}']:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as td:
                p = Path(td); v, *_ = fixture()
                (p/'case.json').write_text(json.dumps({'sample_id': 'software_fixture', 'observer_input': v}))
                advance(p/'case.json', p/'run', 'manual-fixture', 'manual_replay')
                (p/'run/01_discovery.response.txt').write_text(text)
                result = advance(p/'case.json', p/'run', 'manual-fixture', 'manual_replay')
                self.assertEqual(result['prefix_status'], 'PROCESSING_FAILURE')
                self.assertFalse(result['is_measured_model_run'])

    def test_response_hash_preserves_bom_and_line_endings(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td); v, *_ = fixture()
            (p/'case.json').write_text(json.dumps({'sample_id': 'software_fixture', 'observer_input': v}))
            advance(p/'case.json', p/'run', 'manual-fixture', 'manual_replay')
            raw = b'\xef\xbb\xbf{\r\n  "candidates": [],\r\n  "overflow": false\r\n}\r\n'
            (p/'run/01_discovery.response.txt').write_bytes(raw)
            result = advance(p/'case.json', p/'run', 'manual-fixture', 'manual_replay')
            saved_hash = json.loads((p/'run/01_discovery.response_hash.json').read_text(encoding='utf-8'))['sha256']
            self.assertEqual(saved_hash, hashlib.sha256(raw).hexdigest())
            self.assertEqual((p/'run/01_discovery.response.txt').read_bytes(), raw)
            self.assertEqual(result['evidence_tier'], 'S')
            self.assertEqual(result['prefix_status'], 'NO_SUPPORTED_CANDIDATE')


if __name__ == '__main__':
    unittest.main()
