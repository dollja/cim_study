"""CIM pilot, synchronous transport (no background mode, no provider queue).

One ordinary streamed Responses call per stage: send, read the answer, save it.
A call that returns nothing is sent again after a pause (the earlier output was
never observed, so the retry is outcome-blind); every attempt is logged.
Prompts, model, decoding and frozen inputs are those of cim-current-pilot-0.5.

    python src/run_pilot_sync.py --prepare     fix the case list; no provider call
    python src/run_pilot_sync.py           run or resume
    python src/run_pilot_sync.py --status      print saved progress; no provider call

Add --input-set <folder name under data/inputs/> to any command to work on another
frozen input set; each set has its own run, and the budget is shared.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import time
import urllib.error
import urllib.request
import uuid

import pilot
from verify_frozen_inputs import verify

ROOT = Path(__file__).resolve().parents[1]
INPUTS = Path('data/inputs')
FREEZE = INPUTS / 'CIM_INPUTS_20261113_V1'
POINTER = Path('results/current_run.json')
BASE_CONFIG = Path('config/RUN_CONFIG.json')
PRIOR_SPEND = Path('results/prior_spend.json')
ENDPOINT = 'https://api.openai.com/v1/responses'
NETWORK_ERRORS = (OSError, TimeoutError, http.client.HTTPException)
PRICE_IN, PRICE_OUT = 2.5, 15.0  # USD per million tokens, as in the frozen configuration


def use_input_set(name):
    """Point this process at another frozen input set, with its own run pointer."""
    global FREEZE, POINTER
    if not re.fullmatch(r'[A-Za-z0-9_]+', name) or not (INPUTS / name / 'manifest.json').is_file():
        raise ValueError('Unknown input set: ' + name)
    if INPUTS / name != FREEZE:
        FREEZE = INPUTS / name
        POINTER = Path('results') / f'current_run_{name}.json'


class StopRun(Exception):
    """Operator action needed (credentials, quota, budget); nothing is retried."""


class CaseStopped(Exception):
    """This case cannot continue now; other cases still run."""


def use_ipv4_only():
    """Resolve hosts to IPv4 addresses only for this process.

    On the study machine, responses that arrive after a pause were lost on about one IPv6
    connection in ten and on no IPv4 connection (2026-11-16 measurements against public echo
    services). The request content is unaffected.
    """
    original = socket.getaddrinfo
    if getattr(original, 'ipv4_only', False):
        return

    def getaddrinfo(host, port, family=0, *args, **kwargs):
        return original(host, port, socket.AF_INET, *args, **kwargs)

    getaddrinfo.ipv4_only = True
    socket.getaddrinfo = getaddrinfo


def now():
    return datetime.now(timezone.utc).isoformat()


def records(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def api_key():
    """Process environment first, then the Windows per-user variable. Never printed or saved."""
    key = os.environ.get('OPENAI_API_KEY')
    if not key and os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as handle:
                key = winreg.QueryValueEx(handle, 'OPENAI_API_KEY')[0]
        except OSError:
            key = None
    return (key or '').strip()


# ---------------------------------------------------------------- evidence files
def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    """Write a complete file once; existing evidence is never overwritten."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pending_' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_record(path, obj):
    path = Path(path)
    if path.exists():
        if pilot.read(path) != obj:
            raise ValueError('Refusing to change a saved record: ' + str(path))
    else:
        save(path, (json.dumps(obj, indent=2, ensure_ascii=False) + chr(10)).encode('utf-8'))


def append(path, item):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(item, ensure_ascii=False) + chr(10))
        stream.flush()
        os.fsync(stream.fileno())


def completion_text(provider):
    """The model's output text exactly as returned, plus any refusal blocks."""
    blocks = [block for item in provider.get('output', []) if item.get('type') == 'message'
              for block in item.get('content', [])]
    return (''.join(b['text'] for b in blocks if b.get('type') == 'output_text'),
            [b.get('refusal') for b in blocks if b.get('type') == 'refusal'])


def empty_cutoff(provider):
    """True when the provider stopped at the output limit before producing any answer text."""
    return provider.get('status') == 'incomplete' and not completion_text(provider)[0].strip()


def commit_completion(run_dir, step, ctx, raw, request_id, latency, ledger):
    """Save provider record, model text, proof and ledger line; safe to repeat after a crash."""
    run_dir = Path(run_dir)
    provider = json.loads(raw)
    text, refusal = completion_text(provider)
    response_bytes = text.encode('utf-8')
    proof = dict(ctx, response_sha256=sha(response_bytes), provider_sha256=sha(raw),
                 actual_model=provider.get('model'), provider_request_id=request_id,
                 usage=provider.get('usage'), finish_reason=provider.get('status'),
                 refusal=refusal, latency_seconds=latency)
    proof_path = run_dir / (step + '.transport.json')
    if proof_path.exists():
        old = pilot.read(proof_path)
        if any(old.get(k) != proof.get(k) for k in ('request_sha256', 'response_sha256', 'provider_sha256')):
            raise ValueError('Saved completion proof differs; stopped.')
        proof = old
    else:
        write_record(proof_path, proof)
    for suffix, data in [('.provider.json', raw), ('.response.txt', response_bytes)]:
        path = run_dir / (step + suffix)
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError('Saved completion bytes differ; stopped.')
        else:
            save(path, data)
    if not any(e['event'] == 'completion_saved' and e.get('client_request_id') == proof.get('client_request_id')
               for e in records(ledger)):
        append(ledger, dict(proof, event='completion_saved', timestamp_utc=now()))


# ---------------------------------------------------------------- budget
def spend(extra_ledgers=()):
    """Measured cost of every saved completion plus full reservations of attempts with none."""
    measured = unsettled = 0.0
    if PRIOR_SPEND.exists():
        prior = pilot.read(PRIOR_SPEND)
        measured, unsettled = prior['measured_usd'], prior['open_reservations_usd']
    ledgers = sorted(Path('results').glob('*/attempt_ledger.jsonl')) + list(extra_ledgers)
    for ledger in ledgers:
        events = records(ledger)
        done = set()
        for e in events:
            if e['event'] == 'completion_saved':
                done.add(e.get('client_request_id'))
                usage = e.get('usage') or {}
                tokens_in = usage.get('input_tokens', usage.get('prompt_tokens', 0)) or 0
                tokens_out = usage.get('output_tokens', usage.get('completion_tokens', 0)) or 0
                measured += (tokens_in * PRICE_IN + tokens_out * PRICE_OUT) / 1e6
        unsettled += sum(e.get('reserved_usd', 0) for e in events
                         if e['event'] == 'attempt_started' and e.get('client_request_id') not in done)
    return measured, unsettled


# ---------------------------------------------------------------- one provider call
def envelope(request, cfg):
    """Only the harness messages reach the model; identical to earlier runs minus background."""
    assert set(request) == {'stage', 'messages'}
    assert all(set(m) == {'role', 'content'} and m['role'] in {'system', 'user'}
               and isinstance(m['content'], str) for m in request['messages'])
    if cfg['model_id'] != 'gpt-5.4-2026-03-05':
        raise ValueError('This runner is fixed to gpt-5.4-2026-03-05.')
    if cfg['decoding'] != {'reasoning_effort': 'medium', 'json_mode': False, 'temperature': 'provider_default'}:
        raise ValueError('Unsupported decoding configuration.')
    return {'model': cfg['model_id'], 'input': request['messages'],
            'max_output_tokens': cfg['max_output_tokens'], 'reasoning': {'effort': 'medium'},
            'store': True, 'tools': [], 'truncation': 'disabled',
            'service_tier': cfg.get('service_tier', 'default'), 'stream': True}


def token_bound(env):
    """Upper bound, not a count: UTF-8 bytes plus 512 per message plus 512."""
    return sum(len(m['content'].encode('utf-8')) + 512 for m in env['input']) + 512


def headers(cfg, client_id, stream):
    return {'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'], 'Content-Type': 'application/json',
            'Accept': 'text/event-stream' if stream else 'application/json',
            'X-Client-Request-Id': client_id, 'OpenAI-Project': cfg['openai_project_id']}


def post_stream(body, cfg, client_id, sse_path):
    """Returns (final_response_or_None, response_id_or_None, provider_request_id, failure_or_None)."""
    request = urllib.request.Request(ENDPOINT, data=body, headers=headers(cfg, client_id, True))
    response_id = final = failure = provider_request = None
    with urllib.request.urlopen(request, timeout=cfg['sync_timeout_seconds']) as reply:
        provider_request = reply.headers.get('x-request-id')
        data = []
        with Path(sse_path).open('xb') as saved:
            for line in reply:
                saved.write(line)
                saved.flush()
                if line.rstrip(b'\r\n'):
                    if line.startswith(b'data:'):
                        data.append(line[5:].lstrip(b' ').rstrip(b'\r\n'))
                    continue
                if not data:
                    continue
                payload, data = b'\n'.join(data), []
                if payload == b'[DONE]':
                    break
                event = json.loads(payload)
                response = event.get('response')
                if isinstance(response, dict) and re.fullmatch(r'resp_[A-Za-z0-9_-]+', response.get('id') or ''):
                    response_id = response['id']
                kind = event.get('type')
                if kind in {'response.completed', 'response.incomplete'}:
                    final = response
                    break
                if kind in {'response.failed', 'error'}:
                    failure = event
                    break
    return final, response_id, provider_request, failure


def retrieve(response_id, cfg, client_id, folder, prefix):
    """After a broken stream: read the stored response. Returns final dict, or None to send again."""
    deadline = time.monotonic() + cfg['sync_recover_seconds']
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(ENDPOINT + '/' + response_id, headers=headers(cfg, client_id, False))
            with urllib.request.urlopen(request, timeout=30) as reply:
                raw = reply.read()
        except urllib.error.HTTPError as exc:
            exc.read()
            if exc.code in {401, 403}:
                raise StopRun(f'GET HTTP {exc.code}: check the API key and project access.') from None
            if exc.code == 404:
                return None
            time.sleep(cfg['sync_poll_seconds'])
            continue
        except NETWORK_ERRORS:
            time.sleep(cfg['sync_poll_seconds'])
            continue
        try:
            response = json.loads(raw)
        except ValueError:
            time.sleep(cfg['sync_poll_seconds'])
            continue
        if response.get('id') != response_id:
            return None
        if response.get('status') in {'completed', 'incomplete'}:
            save(Path(folder) / (prefix + '.retrieved.json'), raw)
            return response
        if response.get('status') not in {'queued', 'in_progress'}:
            save(Path(folder) / (prefix + '.retrieved.json'), raw)
            return None
        time.sleep(cfg['sync_poll_seconds'])
    return None


def attempt(body, cfg, client_id, folder, prefix):
    """One create. Returns (final, provider_request_id, failure_kind, wait_seconds)."""
    folder = Path(folder)
    try:
        final, response_id, provider_request, failure = post_stream(
            body, cfg, client_id, folder / (prefix + '.stream.sse'))
    except urllib.error.HTTPError as exc:
        text = exc.read()
        save(folder / (prefix + '.http_error.txt'), text)
        if exc.code in {401, 403}:
            raise StopRun(f'HTTP {exc.code}: check the API key and project access.') from None
        if exc.code == 429 and b'insufficient_quota' in text:
            raise StopRun('HTTP 429 insufficient_quota: add credit or raise the project budget.') from None
        if exc.code == 429 or exc.code >= 500 or exc.code == 408:
            wait = exc.headers.get('retry-after') if exc.headers else None
            return None, None, f'http_{exc.code}', float(wait) if wait and wait.replace('.', '', 1).isdigit() else None
        raise CaseStopped(f'HTTP {exc.code}; error body saved. Not retried.') from None
    except NETWORK_ERRORS + (ValueError,) as exc:
        # Identity may be in the partial stream that was saved before the break.
        final, provider_request, failure = None, None, None
        response_id = saved_identity(folder / (prefix + '.stream.sse'))
        if response_id is None:
            return None, None, 'no_answer_' + type(exc).__name__, None
    if final is None and failure is None and response_id:
        final = retrieve(response_id, cfg, client_id, folder, prefix)
        if final is None:
            return None, provider_request, 'stream_broken_no_completion', None
    if failure is not None:
        save(folder / (prefix + '.failure_event.json'), json.dumps(failure, ensure_ascii=False).encode())
        return None, provider_request, 'provider_failed', None
    return final, provider_request, None, None


def saved_identity(sse_path):
    if not Path(sse_path).exists():
        return None
    for block in Path(sse_path).read_bytes().replace(b'\r\n', b'\n').split(b'\n\n')[:-1]:
        data = b'\n'.join(line[5:].lstrip(b' ') for line in block.split(b'\n') if line.startswith(b'data:'))
        try:
            response = json.loads(data).get('response')
        except (ValueError, AttributeError):
            continue
        if isinstance(response, dict) and re.fullmatch(r'resp_[A-Za-z0-9_-]+', response.get('id') or ''):
            return response['id']
    return None


# ---------------------------------------------------------------- one case
def run_case(case, run_dir, cfg, ledger, state):
    run_dir, ledger = Path(run_dir), Path(ledger)
    pilot.write_new(run_dir / 'run_configuration.json', cfg)
    cid = pilot.read(case)['sample_id']
    while True:
        for response in run_dir.glob('*.response.txt'):
            step = response.name.removesuffix('.response.txt')
            proof = pilot.read(run_dir / (step + '.transport.json'))
            if (sha(response.read_bytes()) != proof['response_sha256']
                    or sha((run_dir / (step + '.request.json')).read_bytes()) != proof['request_sha256']
                    or sha((run_dir / (step + '.provider.json')).read_bytes()) != proof['provider_sha256']):
                raise ValueError('Saved completion no longer matches its proof; stopped.')
        result = pilot.advance(case, run_dir, cfg['model_id'], 'external_model')
        if result.get('status') != 'AWAITING_MODEL_RESPONSE':
            return result
        pending = [p for p in run_dir.glob('*.request.json')
                   if not p.with_name(p.name.replace('.request.json', '.response.txt')).exists()]
        if len(pending) != 1:
            raise ValueError('Expected exactly one next request.')
        request_path = pending[0]
        step = request_path.name.removesuffix('.request.json')
        env = envelope(pilot.read(request_path), cfg)
        bound = token_bound(env)
        if bound + cfg['max_output_tokens'] > cfg['context_limit'] or bound > 272000:
            raise CaseStopped('Prompt exceeds the conservative size bound; nothing is truncated.')
        reserve = (bound * PRICE_IN + cfg['max_output_tokens'] * PRICE_OUT) / 1e6
        body = json.dumps(env, ensure_ascii=False).encode('utf-8')
        write_record(run_dir / (step + '.envelope.json'), env)
        folder = run_dir / 'attempts'
        folder.mkdir(exist_ok=True)
        tries = 0
        while True:
            earlier = [e for e in records(ledger) if e['event'] == 'attempt_started'
                       and e['case_id'] == cid and e['step'] == step]
            if tries >= cfg['sync_attempts_per_stage_per_launch'] or len(earlier) >= cfg['sync_attempts_per_stage_total']:
                raise CaseStopped(f'{step}: no completion after {tries} attempts this launch; resumable.')
            measured, unsettled = spend()
            if measured + unsettled + reserve > cfg['total_authorized_ceiling_usd']:
                raise StopRun(f'Budget ceiling reached (measured ${measured:.2f} + open reservations ${unsettled:.2f}).')
            tries += 1
            ordinal = len(earlier) + 1
            ctx = {'case_id': cid, 'step': step, 'attempt': ordinal, 'timestamp_utc': now(),
                   'reserved_usd': reserve, 'client_request_id': str(uuid.uuid4()),
                   'request_sha256': sha(request_path.read_bytes()),
                   'messages_sha256': pilot.digest(env['input']), 'input_token_upper_bound': bound,
                   'envelope': str(run_dir / (step + '.envelope.json'))}
            append(ledger, dict(ctx, event='attempt_started'))
            started = time.monotonic()
            final, provider_request, failure, wait = attempt(
                body, cfg, ctx['client_request_id'], folder, f'{step}.attempt{ordinal}')
            if final is not None and final.get('model') != cfg['model_id']:
                save(folder / f'{step}.attempt{ordinal}.unexpected_model.json',
                          json.dumps(final, ensure_ascii=False).encode())
                raise CaseStopped('Provider answered with a different model; preserved, not used.')
            if final is not None and empty_cutoff(final):
                # The output limit was spent before any answer text: nothing to evaluate, so send again.
                save(folder / f'{step}.attempt{ordinal}.empty_cutoff.json',
                     json.dumps(final, ensure_ascii=False).encode())
                final, failure = None, 'empty_reply_at_output_limit'
            if final is not None:
                raw = json.dumps(final, ensure_ascii=False).encode('utf-8')
                commit_completion(run_dir, step, ctx, raw, provider_request,
                                       time.monotonic() - started, ledger)
                state['consecutive_failures'] = 0
                state['completions'] += 1
                print(f'  {cid} {step}: saved ({time.monotonic() - started:.0f}s)', flush=True)
                break
            append(ledger, dict(ctx, event='attempt_failed', failure=failure, ended_utc=now(),
                                     latency_seconds=time.monotonic() - started))
            state['consecutive_failures'] += 1
            if state['consecutive_failures'] >= cfg['sync_consecutive_failure_limit']:
                raise StopRun(f'{state["consecutive_failures"]} calls in a row returned nothing; provider looks unavailable.')
            pause = wait if wait is not None else min(cfg['sync_backoff_seconds'] * 2 ** (tries - 1), cfg['sync_backoff_max_seconds'])
            print(f'  {cid} {step}: attempt {ordinal} returned nothing ({failure}); retrying in {int(pause)}s', flush=True)
            time.sleep(pause)


# ---------------------------------------------------------------- run level
def usable_predictions():
    """Cases that already hold a non-failure prediction under the current prompts."""
    found = {}
    for prediction in Path('runs').glob('*/*/prediction.json'):
        config = Path('results') / prediction.parent.parent.name / 'condition_configuration.json'
        if (config.exists() and pilot.read(config).get('prompt_revision') == pilot.VERSION
                and pilot.read(prediction)['prefix_status'] != 'PROCESSING_FAILURE'):
            found[prediction.parent.name] = prediction.parent.parent.name
    return found


def prepare(all_cases=False):
    if POINTER.exists():
        run_id = pilot.read(POINTER)['run_id']
        return run_id, pilot.read(Path('results') / run_id / 'condition_configuration.json')
    integrity = verify(FREEZE)
    if not integrity['valid']:
        raise ValueError('Frozen input verification failed; nothing prepared.')
    cases = sorted(p.stem for p in (FREEZE / 'prospective/observer_cases').glob('*.json'))
    already = usable_predictions()
    first = [c for c in cases if c not in already]
    active = first + ([c for c in cases if c in already] if all_cases else [])
    cfg = pilot.read(BASE_CONFIG)
    measured, unsettled = spend()
    cfg.update(condition_id='CIM_STAGED_STRICT_S_V05_SYNC_V1', input_freeze_id=FREEZE.name,
               provider_or_runtime='OpenAI Responses API, synchronous streamed call with explicit project routing',
               transport_api='responses_sync_stream', transport_revision='runtime_sync_v1',
               sync_timeout_seconds=180, sync_recover_seconds=300, sync_poll_seconds=5,
               sync_attempts_per_stage_per_launch=6, sync_attempts_per_stage_total=18,
               sync_backoff_seconds=20, sync_backoff_max_seconds=300, sync_consecutive_failure_limit=8,
               network_address_family='ipv4',
               budget_rule='Measured token cost of saved completions plus full upper-bound reservation of every attempt without a completion, across all runs, must stay within total_authorized_ceiling_usd.',
               measured_usd_before_this_run=round(measured, 4),
               open_reservations_usd_before_this_run=round(unsettled, 4),
               notes='One ordinary streamed call per stage. A call that returns no completion is sent again; '
                     'no output of the earlier attempt was observed, and every attempt is logged.')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_strictS_gpt54_sync_v1'
    out = Path('results') / run_id
    out.mkdir()
    pilot.write_new(out / 'condition_configuration.json', cfg)
    pilot.write_new(out / 'freeze_validation.json', integrity)
    source = [Path('src/pilot.py'), Path('src/run_pilot_sync.py'), Path('src/verify_frozen_inputs.py')]
    pilot.write_new(out / 'source_identity.json', {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source})
    pilot.write_new(out / 'execution_order.json', {
        'all_accepted_case_ids': cases, 'active_case_ids': active,
        'not_scheduled_existing_current_prompt_prediction': {c: r for c, r in already.items() if c not in active},
        'rule': 'Sorted cases without a non-failure prediction under the current prompts'
                + ('; then the cases that have one, so all 20 share this condition.' if all_cases else '.')
                + ' Fixed before any call of this condition; no model output informs selection.'})
    pilot.write_new(POINTER, {'run_id': run_id})
    return run_id, cfg


def progress(run_id):
    out = Path('results') / run_id
    order = pilot.read(out / 'execution_order.json')
    events = records(out / 'attempt_ledger.jsonl')
    last = {}
    for e in records(out / 'case_events.jsonl'):
        last[e['case_id']] = e
    rows = []
    for cid in order['all_accepted_case_ids']:
        prediction = Path('runs') / run_id / cid / 'prediction.json'
        mine = [e for e in events if e.get('case_id') == cid]
        if prediction.exists():
            status = pilot.read(prediction)['prefix_status']
        elif cid in order['active_case_ids']:
            status = last.get(cid, {}).get('status', 'IN_PROGRESS' if mine else 'NOT_STARTED')
        else:
            status = 'NOT_SCHEDULED_HAS_EARLIER_PREDICTION'
        rows.append({'case_id': cid, 'status': status,
                     'completions': sum(e['event'] == 'completion_saved' for e in mine),
                     'failed_attempts': sum(e['event'] == 'attempt_failed' for e in mine),
                     'prediction': str(prediction) if prediction.exists() else None})
    measured, unsettled = spend()
    report = {'run_id': run_id, 'recorded_utc': now(), 'scheduled': len(order['active_case_ids']),
              'predictions': sum(r['prediction'] is not None for r in rows),
              'completions': sum(r['completions'] for r in rows),
              'failed_attempts': sum(r['failed_attempts'] for r in rows),
              'measured_usd_all_runs': round(measured, 2), 'open_reservations_usd_all_runs': round(unsettled, 2),
              'cases': rows}
    temp = out / 'progress.tmp'
    temp.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, out / 'progress.json')
    return report


def reopen_failures(run_id):
    """Set aside PROCESSING_FAILURE predictions so the next pass evaluates those cases again.

    Nothing is deleted. Saved model replies are reused as they are; only a reply that
    was cut off empty at the output limit is set aside, so that one call is sent again.
    """
    out = Path('results') / run_id
    reopened = []
    for case_dir in sorted((Path('runs') / run_id).iterdir()):
        prediction = case_dir / 'prediction.json'
        if not prediction.exists() or pilot.read(prediction)['prefix_status'] != 'PROCESSING_FAILURE':
            continue
        kept = case_dir / 'superseded'
        kept.mkdir(exist_ok=True)
        round_no = len(list(kept.glob('prediction.*.json'))) + 1
        moved = []
        for provider in sorted(case_dir.glob('*.provider.json')):
            if empty_cutoff(json.loads(provider.read_bytes())):
                step = provider.name.removesuffix('.provider.json')
                for suffix in ('.provider.json', '.response.txt', '.transport.json', '.response_hash.json'):
                    path = case_dir / (step + suffix)
                    if path.exists():
                        os.replace(path, kept / f'{step}.{round_no}{suffix}')
                moved.append(step)
        error = pilot.read(prediction).get('error')
        for name in ('prediction', 'identity'):
            os.replace(case_dir / (name + '.json'), kept / f'{name}.{round_no}.json')
        append(out / 'case_events.jsonl', {'case_id': case_dir.name, 'timestamp_utc': now(),
                                           'status': 'REOPENED_AFTER_PROCESSING_FAILURE', 'earlier_error': error,
                                           'empty_replies_set_aside': moved,
                                           'pilot_sha256': hashlib.sha256(Path(pilot.__file__).read_bytes()).hexdigest(),
                                           'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        reopened.append(case_dir.name)
    return reopened


def alive(pid):
    if os.name == 'nt':
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def execute(run_id, cfg, max_cases=None):
    out = Path('results') / run_id
    lock = out / 'run.lock'
    if lock.exists():
        holder = pilot.read(lock).get('pid')
        if holder and alive(holder):
            raise ValueError(f'This run is already active in process {holder}.')
        lock.unlink()
    lock.write_text(json.dumps({'pid': os.getpid(), 'started_utc': now()}), encoding='utf-8')
    state = {'consecutive_failures': 0, 'completions': 0}
    use_ipv4_only()
    try:
        if not verify(FREEZE)['valid']:
            raise ValueError('Frozen inputs changed; execution stopped.')
        order = pilot.read(out / 'execution_order.json')
        done = 0
        for cid in order['active_case_ids']:
            case_dir = Path('runs') / run_id / cid
            if (case_dir / 'prediction.json').exists():
                continue
            if max_cases is not None and done >= max_cases:
                break
            done += 1
            print(f'{cid}: running', flush=True)
            event = {'case_id': cid, 'timestamp_utc': now()}
            try:
                result = run_case(FREEZE / 'prospective/observer_cases' / (cid + '.json'),
                                  case_dir, cfg, out / 'attempt_ledger.jsonl', state)
                event['status'] = result.get('prefix_status', result.get('status', 'UNKNOWN_RESULT'))
                print(f'{cid}: {event["status"]}', flush=True)
            except CaseStopped as exc:
                event.update(status='TRANSPORT_INCOMPLETE', detail=str(exc))
                print(f'{cid}: paused - {exc}', flush=True)
            except StopRun as exc:
                event.update(status='RUN_STOPPED', detail=str(exc))
                append(out / 'case_events.jsonl', event)
                progress(run_id)
                print('Run stopped: ' + str(exc), flush=True)
                return 2
            except Exception as exc:  # one bad case must not end the run
                event.update(status='LOCAL_ERROR', detail=type(exc).__name__ + ': ' + str(exc))
                print(f'{cid}: local error - {event["detail"]}', flush=True)
            append(out / 'case_events.jsonl', event)
            progress(run_id)
        report = progress(run_id)
        print(f'Finished pass: {report["predictions"]} predictions; {report["scheduled"]} cases scheduled.', flush=True)
        missing = [c for c in order['active_case_ids'] if not (Path('runs') / run_id / c / 'prediction.json').exists()]
        return 0 if not missing else 2
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--all-cases', action='store_true', help='At preparation: schedule all 20 cases, those with an earlier prediction last.')
    parser.add_argument('--input-set', help='Folder name under data/inputs/ (default: the first input set).')
    parser.add_argument('--retry-failures', action='store_true',
                        help='Set aside PROCESSING_FAILURE predictions and evaluate those cases again from the saved replies.')
    parser.add_argument('--max-cases', type=int, help='Stop after this many cases in this launch (smoke test).')
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.input_set:
        use_input_set(args.input_set)
    if args.status:
        if not POINTER.exists():
            print('No synchronous run prepared.')
            return 0
        report = progress(pilot.read(POINTER)['run_id'])
        for row in report['cases']:
            print(f'{row["case_id"]}: {row["status"]} ({row["completions"]} completions, {row["failed_attempts"]} failed attempts)')
        print(f'Predictions {report["predictions"]}/{report["scheduled"]} scheduled. Measured cost all runs ${report["measured_usd_all_runs"]}; open reservations ${report["open_reservations_usd_all_runs"]}.')
        return 0
    run_id, cfg = prepare(args.all_cases)
    report = progress(run_id)
    print(f'Run {run_id}: {report["scheduled"]} cases scheduled, {report["predictions"]} predictions saved.', flush=True)
    if args.retry_failures:
        print('Reopened: ' + (', '.join(reopen_failures(run_id)) or 'none'), flush=True)
    if args.prepare:
        print('Prepared only; zero provider calls.')
        return 0
    key = api_key() or getpass.getpass('OpenAI API key (hidden): ').strip()
    if not key:
        raise ValueError('No API key available; no provider call sent.')
    previous = os.environ.get('OPENAI_API_KEY')
    os.environ['OPENAI_API_KEY'] = key
    try:
        return execute(run_id, cfg, args.max_cases)
    finally:
        if previous is None:
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = previous


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nStopped by operator. Saved records preserved; run the same command to resume.')
        raise SystemExit(130)
    except (ValueError, OSError) as exc:
        print('Pilot stopped: ' + str(exc), flush=True)
        raise SystemExit(1)
