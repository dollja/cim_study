"""Synchronous-runner fault injection. Synthetic provider data only; zero network calls."""
import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error
import uuid
from pathlib import Path
from unittest.mock import patch

import pilot
import run_pilot_sync as sync
from tests.test_pilot import fixture

MODEL = 'gpt-5.4-2026-03-05'
CFG = {'model_id': MODEL, 'provider_or_runtime': 'mock', 'context_limit': 1050000, 'max_output_tokens': 8192,
       'decoding': {'reasoning_effort': 'medium', 'json_mode': False, 'temperature': 'provider_default'},
       'operator': 'software_test_only', 'evidence_tier': 'S', 'openai_project_id': 'proj_MOCKONLY',
       'service_tier': 'default'}
TEXT = '{"candidates":[],"overflow":false}'


def response(rid, status, text=None, model=MODEL):
    body = {'id': rid, 'status': status, 'model': model, 'output': [], 'usage': None, 'error': None}
    if text is not None:
        body['output'] = [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]
        body['usage'] = {'input_tokens': 1000, 'output_tokens': 1000}
    return body


def sse(*events):
    return b''.join(('event: ' + kind + '\ndata: ' + json.dumps({'type': kind, 'response': body}) + '\n\n').encode()
                    for kind, body in events)


def good(rid='resp_A'):
    return Stream(sse(('response.created', response(rid, 'in_progress')),
                      ('response.completed', response(rid, 'completed', TEXT))))


class Stream:
    status = 200
    headers = {'x-request-id': 'req_MOCK_ONLY', 'Content-Type': 'text/event-stream'}

    def __init__(self, data, then=None):
        self.data, self.then = data, then

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __iter__(self):
        yield from io.BytesIO(self.data)
        if self.then:
            raise self.then

    def read(self):
        return self.data


class Provider:
    def __init__(self, posts, gets=None):
        self.posts, self.gets = list(posts), dict(gets or {})
        self.post_bodies, self.get_urls = [], []

    def urlopen(self, request, timeout=None):
        if request.data is None:
            self.get_urls.append(request.full_url)
            rid = request.full_url.rsplit('/', 1)[1]
            queue = self.gets[rid]
            item = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(item, BaseException):
                raise item
            return Stream(json.dumps(item).encode())
        self.post_bodies.append(json.loads(request.data))
        item = self.posts.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def http_error(code, body=b'{}', headers=None):
    return urllib.error.HTTPError('u', code, 'mock', headers or {}, io.BytesIO(body))


class SyncRunnerTests(unittest.TestCase):
    def setUp(self):
        self.origin = Path.cwd()
        self.root = Path(tempfile.mkdtemp(prefix='CIM_MOCK_ONLY_SYNC_'))
        os.chdir(self.root)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(os.chdir, self.origin)
        self.case = self.root / 'MOCK_ONLY.json'
        pilot.write_new(self.case, {'sample_id': 'MOCK_ONLY', 'study_role': 'engineering_fixture',
                                    'observer_input': fixture()[0]})
        self.cfg = dict(CFG, transport_api='responses_sync_stream', total_authorized_ceiling_usd=100.0,
                        sync_timeout_seconds=1, sync_recover_seconds=1, sync_poll_seconds=0,
                        sync_attempts_per_stage_per_launch=3, sync_attempts_per_stage_total=5,
                        sync_backoff_seconds=20, sync_backoff_max_seconds=300, sync_consecutive_failure_limit=8)
        self.run_dir = self.root / 'runs' / 'SYNC' / 'MOCK_ONLY'
        self.ledger = self.root / 'results' / 'SYNC' / 'attempt_ledger.jsonl'
        self.ledger.parent.mkdir(parents=True)
        self.state = {'consecutive_failures': 0, 'completions': 0}
        for item in (patch.dict(sync.os.environ, {'OPENAI_API_KEY': 'MOCK_ONLY'}),
                     patch.object(sync.time, 'sleep')):
            self.sleep = item.start()
            self.addCleanup(item.stop)

    def go(self, mock, cfg=None):
        with patch.object(sync.urllib.request, 'urlopen', side_effect=mock.urlopen):
            return sync.run_case(self.case, self.run_dir, cfg or self.cfg, self.ledger, self.state)

    def count(self, name):
        return sum(e['event'] == name for e in sync.records(self.ledger))

    def test_plain_call_saves_prediction_and_resume_needs_no_network(self):
        mock = Provider([good()])
        result = self.go(mock)
        self.assertEqual(result['prefix_status'], 'NO_SUPPORTED_CANDIDATE')
        self.assertEqual((self.run_dir / '01_discovery.response.txt').read_bytes(), TEXT.encode())
        body = mock.post_bodies[0]
        self.assertNotIn('background', body)
        self.assertTrue(body['stream'])
        self.assertEqual(body['input'], pilot.read(self.run_dir / '01_discovery.request.json')['messages'])
        self.assertEqual(body['model'], MODEL)
        self.assertEqual(body['reasoning'], {'effort': 'medium'})
        self.assertEqual(self.go(Provider([])), result)
        self.assertEqual((self.count('attempt_started'), self.count('completion_saved')), (1, 1))

    def test_call_with_no_answer_is_sent_again(self):
        mock = Provider([TimeoutError('no headers'), good()])
        self.assertEqual(self.go(mock)['prefix_status'], 'NO_SUPPORTED_CANDIDATE')
        self.assertEqual(len(mock.post_bodies), 2)
        self.assertEqual(mock.post_bodies[0], mock.post_bodies[1])
        self.assertEqual((self.count('attempt_started'), self.count('attempt_failed')), (2, 1))
        self.assertEqual(self.sleep.call_args_list[0].args[0], 20)

    def test_broken_stream_is_recovered_by_reading_the_stored_response(self):
        broken = Stream(sse(('response.created', response('resp_A', 'in_progress'))), TimeoutError('stall'))
        mock = Provider([broken], {'resp_A': [response('resp_A', 'in_progress'), response('resp_A', 'completed', TEXT)]})
        self.assertEqual(self.go(mock)['prefix_status'], 'NO_SUPPORTED_CANDIDATE')
        self.assertEqual(len(mock.post_bodies), 1)
        self.assertEqual(len(mock.get_urls), 2)
        self.assertEqual(self.count('attempt_failed'), 0)

    def test_broken_stream_whose_response_died_is_sent_again(self):
        broken = Stream(sse(('response.created', response('resp_A', 'in_progress'))), ConnectionResetError())
        mock = Provider([broken, good('resp_B')], {'resp_A': [response('resp_A', 'cancelled')]})
        self.assertEqual(self.go(mock)['prefix_status'], 'NO_SUPPORTED_CANDIDATE')
        self.assertEqual(len(mock.post_bodies), 2)
        proof = pilot.read(self.run_dir / '01_discovery.transport.json')
        self.assertEqual(proof['attempt'], 2)

    def test_provider_failed_event_and_rate_limit_are_retried(self):
        failed = Stream(sse(('response.created', response('resp_A', 'in_progress')),
                            ('response.failed', response('resp_A', 'failed'))))
        mock = Provider([failed, http_error(429, b'{"error":{"code":"rate_limit_exceeded"}}', {'retry-after': '7'}),
                         good('resp_C')])
        self.assertEqual(self.go(mock)['prefix_status'], 'NO_SUPPORTED_CANDIDATE')
        self.assertEqual(self.count('attempt_failed'), 2)
        self.assertEqual(self.sleep.call_args_list[1].args[0], 7.0)

    def test_bad_key_or_empty_quota_stops_the_run_without_retry(self):
        for error in (http_error(401), http_error(429, b'{"error":{"code":"insufficient_quota"}}')):
            mock = Provider([error, good()])
            with self.assertRaises(sync.StopRun):
                self.go(mock)
            self.assertEqual(len(mock.posts), 1)

    def test_attempt_limit_pauses_case_and_later_launch_continues(self):
        mock = Provider([TimeoutError()] * 3)
        with self.assertRaises(sync.CaseStopped):
            self.go(mock)
        self.assertEqual(len(mock.post_bodies), 3)
        self.assertEqual(self.go(Provider([good()]))['prefix_status'], 'NO_SUPPORTED_CANDIDATE')
        self.assertEqual(self.count('attempt_started'), 4)

    def test_many_failures_in_a_row_stop_the_run(self):
        cfg = dict(self.cfg, sync_consecutive_failure_limit=2)
        mock = Provider([TimeoutError()] * 3)
        with self.assertRaises(sync.StopRun):
            self.go(mock, cfg)
        self.assertEqual(len(mock.post_bodies), 2)

    def test_wrong_model_is_preserved_and_not_used(self):
        other = Stream(sse(('response.completed', response('resp_A', 'completed', TEXT, model='other-model'))))
        with self.assertRaises(sync.CaseStopped):
            self.go(Provider([other]))
        self.assertFalse((self.run_dir / '01_discovery.response.txt').exists())

    def test_budget_ceiling_blocks_before_sending(self):
        cfg = dict(self.cfg, total_authorized_ceiling_usd=0.01)
        mock = Provider([good()])
        with self.assertRaises(sync.StopRun):
            self.go(mock, cfg)
        self.assertEqual(mock.post_bodies, [])

    def test_spend_uses_measured_cost_for_completions_and_reservation_otherwise(self):
        self.go(Provider([TimeoutError(), good()]))
        measured, unsettled = sync.spend()
        self.assertAlmostEqual(measured, (1000 * 2.5 + 1000 * 15) / 1e6)
        failed = [e for e in sync.records(self.ledger) if e['event'] == 'attempt_started'][0]
        self.assertAlmostEqual(unsettled, failed['reserved_usd'])

    def test_execute_continues_past_a_paused_case_and_reports_progress(self):
        out = Path('results/RUN')
        out.mkdir(parents=True)
        (out / 'execution_order.json').write_text(json.dumps(
            {'all_accepted_case_ids': ['A', 'B'], 'active_case_ids': ['A', 'B']}))

        def fake(case, run_dir, cfg, ledger, state):
            if case.stem == 'A':
                raise sync.CaseStopped('mock: no completion')
            run_dir.mkdir(parents=True)
            (run_dir / 'prediction.json').write_text(json.dumps({'prefix_status': 'UNRESOLVED'}))
            return {'prefix_status': 'UNRESOLVED'}

        with patch.object(sync, 'verify', return_value={'valid': True}), patch.object(sync, 'run_case', side_effect=fake):
            self.assertEqual(sync.execute('RUN', self.cfg), 2)
        report = pilot.read(out / 'progress.json')
        self.assertEqual([r['status'] for r in report['cases']], ['TRANSPORT_INCOMPLETE', 'UNRESOLVED'])
        self.assertEqual(report['predictions'], 1)
        self.assertFalse((out / 'run.lock').exists())


if __name__ == '__main__':
    unittest.main()
