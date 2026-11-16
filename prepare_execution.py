"""Record local CIM validation, readiness, provenance and Chapter 5 status.

No model inference, human judgments or frozen-input edits are performed here.
Run from the project root. Every invocation creates a fresh UTC RUN_ID.
"""
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
import pilot
import review_tools
from review_key_codec import to_technical_reviews
from verify_frozen_inputs import verify
from build_chapter5 import build

ROOT = Path(__file__).resolve().parent
FREEZE = Path('freezes/CIM_INPUTS_20261113_V1')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value):
    pilot.write_new(path, value)

def csv_out(path, rows):
    with Path(path).open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows)

def main():
    os.chdir(ROOT)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_strictS_gpt54'
    out = Path('results') / run_id
    out.mkdir(parents=True)
    (out / 'logs').mkdir()
    run_root = Path('runs') / run_id
    run_root.mkdir(parents=True)
    commands = []
    def command(args, label):
        started = datetime.now(timezone.utc).isoformat()
        proc = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
        (out / 'logs' / (label + '.stdout.txt')).write_text(proc.stdout, encoding='utf-8')
        (out / 'logs' / (label + '.stderr.txt')).write_text(proc.stderr, encoding='utf-8')
        record = {'argv': args, 'display': subprocess.list2cmdline(args), 'cwd': str(ROOT),
                  'started_utc': started, 'exit_code': proc.returncode,
                  'stdout': str(out / 'logs' / (label + '.stdout.txt')),
                  'stderr': str(out / 'logs' / (label + '.stderr.txt'))}
        commands.append(record)
        dump(out / 'logs' / (label + '.command.json'), record)
        return proc
    command(['python', 'verify_frozen_inputs.py'], '01_freeze')
    observer = str(FREEZE / 'prospective/observer_inputs')
    command(['python', 'review_tools.py', 'validate', 'REVIEWS.json', '--observer-dir', observer], '02_r1')
    command(['python', 'review_tools.py', 'validate', 'REVIEWS.json', '--observer-dir', observer, '--complete'], '03_r1_complete')
    command(['python', 'review_tools.py', 'validate', 'reviews/reader_2/REVIEWS.json', '--observer-dir', observer, '--complete'], '04_r2_complete')
    command(['python', 'prospective/validate_candidates.py', '--root', str(FREEZE / 'prospective'), '--out', 'validation/candidates_' + run_id + '.json'], '05_candidates')
    command(['python', 'prospective/validate_candidates.py', '--root', str(FREEZE / 'prospective'), '--out', 'validation/frozen_' + run_id + '.json'], '06_frozen_candidates')
    command(['python', '-m', 'unittest', 'tests.test_model_transport', '-v'], '07_transport_tests')
    integrity = verify()
    dump(out / 'freeze_validation.json', integrity)
    raw_r1 = review_tools.load_json('REVIEWS.json')
    r1 = to_technical_reviews(raw_r1)
    r2 = to_technical_reviews(review_tools.load_json('reviews/reader_2/REVIEWS.json'))
    v1 = review_tools.validate_reviews(raw_r1, observer)
    v2 = review_tools.validate_reviews(r2, observer)
    dump(out / 'r1_validation.json', v1); dump(out / 'r2_validation.json', v2)
    availability = {'recorded_utc': datetime.now(timezone.utc).isoformat(),
                    'credential_presence_only': {'OPENAI_API_KEY': bool(os.environ.get('OPENAI_API_KEY'))},
                    'installed_clients': {x: bool(importlib.util.find_spec(x)) for x in ['openai', 'anthropic', 'torch', 'transformers', 'tiktoken']},
                    'ollama_on_path': bool(shutil.which('ollama')),
                    'transport': 'standard-library urllib; no client installation required',
                    'model_choice': 'user selected GPT-5.4 API', 'authorized_ceiling_usd': 100,
                    'credential_scope': 'process environment; Codex login tokens are not reused as API credentials'}
    dump(out / 'runtime_availability.json', availability)
    config = pilot.read('RUN_CONFIG.example.json')
    config.update(model_id='gpt-5.4-2026-03-05', provider_or_runtime='OpenAI Chat Completions API',
                  context_limit=1050000, max_output_tokens=8192,
                  decoding={'reasoning_effort': 'medium', 'json_mode': False, 'temperature': 'provider_default'},
                  operator='Codex implementation agent under user authorization', monetary_ceiling_usd=100,
                  max_distinct_requests_per_case=46, max_distinct_requests_condition=920,
                  max_provider_attempts_condition=940, max_attempts_per_stage=2,
                  max_extra_transient_retries_condition=20, automatic_retries=0,
                  timeout_seconds=180, token_accounting='UTF-8 byte upper bound plus 512 framing tokens per message and 512 fixed; never a measured count',
                  price_input_usd_per_million=2.5, price_output_usd_per_million=15,
                  pricing_source='https://developers.openai.com/api/docs/models/gpt-5.4',
                  notes='User chose GPT-5.4 and raised whole-condition ceiling to USD100. No seed set; provider-default temperature. No API JSON constraint. No calls without OPENAI_API_KEY. Conservative reservations retain full attempt cost after errors; no automatic retries.')
    dump(out / 'condition_configuration.json', config)
    with (FREEZE / 'pilot_selection.csv').open(encoding='utf-8-sig', newline='') as f:
        selection = list(csv.DictReader(f))
    accepted = set(pilot.read('selection_records/ACCEPTED_SELECTION_20261113.json')['case_ids'])
    rows, views = [], {}
    for selected in sorted(selection, key=lambda r: r['sample_id']):
        cid = selected['sample_id']; path = FREEZE / 'prospective/observer_inputs' / (cid + '.json')
        view = pilot.check_view(pilot.read(path)); views[cid] = view
        wrapper = pilot.read(FREEZE / 'prospective/observer_cases' / (cid + '.json'))
        curator = pilot.read(FREEZE / 'prospective/curator_cases' / (cid + '.json'))
        local_errors = list(integrity['cases'][cid]['errors'])
        if cid not in accepted or selected['selected'].lower() != 'true': local_errors.append('Selection authority mismatch')
        if wrapper['study_role'] != 'pilot' or curator['study_role'] != 'pilot': local_errors.append('Role mismatch')
        if wrapper['observer_input'] != view or curator['observer_input'] != view: local_errors.append('View copies differ')
        ready = not local_errors and integrity['valid']
        blockers = list(local_errors)
        if not availability['credential_presence_only']['OPENAI_API_KEY']: blockers.append('OPENAI_API_KEY absent from process environment')
        rows.append({'case_id': cid, 'source_id': selected['source_conversation'], 'prefix_cutoff': selected['cutoff_id'],
                     'prefix_turn_count': len(view['dialogue_prefix']), 'raw_observer_sha256': sha(path),
                     'canonical_observer_sha256': pilot.digest(view), 'selected': cid in accepted,
                     'study_role': wrapper['study_role'], 'context_verification_basis': 'recorded user/r1 attestation; assisted_development',
                     'source_cluster': selected['map_pair_or_game_group'], 'cluster_independence_verified': False,
                     'r1_complete': v1['cases'][cid]['complete'], 'r1_gaps': v1['cases'][cid]['missing_for_completion'],
                     'r2_complete': v2['cases'][cid]['complete'], 'r2_gaps': v2['cases'][cid]['missing_for_completion'],
                     'input_and_selection_ready': ready, 'model_execution_eligible': ready and not blockers,
                     'model_execution_blockers': blockers, 'final_scoring_eligible': False,
                     'final_reference_gaps': ['separate actual r2 submission', 'human adjudication', 'candidate-specific chain review after prediction'],
                     'next_execution_action': 'Configure OPENAI_API_KEY securely in runner environment; execute fixed condition',
                     'next_reference_action': '; '.join(v1['cases'][cid]['missing_for_completion'] + ['r2 and adjudication pending'])})
    overlaps = []
    for i, a in enumerate(rows):
        for b in rows[i+1:]:
            common = {t['utterance_id'] for t in views[a['case_id']]['dialogue_prefix']} & {t['utterance_id'] for t in views[b['case_id']]['dialogue_prefix']}
            if common: overlaps.append({'case_a': a['case_id'], 'case_b': b['case_id'], 'shared_turn_ids': sorted(common)})
    groups = {}
    for r in rows: groups.setdefault(r['source_cluster'], []).append(r['case_id'])
    dump(out / 'source_dependence.json', {'provisional_groups': groups, 'overlapping_prefix_windows': overlaps,
                                         'limits': 'Different source turn IDs do not prove distinct participants or game sessions. Map sharing is retained; session independence is unverified.'})
    dump(out / 'readiness.json', rows); csv_out(out / 'readiness.csv', rows)
    order = [r['case_id'] for r in rows]
    dump(out / 'prespecified_order.json', {'case_ids': order, 'smoke_case': order[0], 'rule': 'sorted accepted sample IDs before any model outputs'})
    # Empty ledger is intentional: validation and dry runs are not provider attempts.
    (out / 'attempt_ledger.jsonl').write_text('', encoding='utf-8')
    execution = [{'case_id': r['case_id'], 'status': 'BLOCKED_CREDENTIALS', 'provider_attempts': 0,
                  'terminal_prediction': False, 'successfully_processed': False, 'processing_failure': False,
                  'transport_failures': 0, 'requests': [], 'replies': [], 'provider_records': [],
                  'blockers': r['model_execution_blockers']} for r in rows]
    dump(out / 'execution_table.json', execution); csv_out(out / 'execution_table.csv', execution)
    command(['python', 'report_results.py', str(run_root), '--out', str(out / 'execution_only.json')], '08_execution_report')
    # Genuine no-call transport preflight, separate from test mocks.
    first = FREEZE / 'prospective/observer_cases' / (order[0] + '.json')
    command(['python', 'run_model.py', str(first), str(run_root / order[0]), '--config', str(out / 'condition_configuration.json'), '--ledger', str(out / 'attempt_ledger.jsonl'), '--preflight'], '09_transport_preflight')
    files = set()
    for pattern in ['*.py', '*.ps1', 'tests/test_model_transport.py', 'REVIEWS*.json', 'RUN_CONFIG*.json', 'reviews/**/*.json', 'review_provenance/**/*.json',
                    'schemas/*.json', 'context_reviews/*.json', 'selection_records/*.json', 'freezes/CIM_INPUTS_20261113_V1/**/*',
                    'history/pre_context_confirmation_20261113/REVIEWS*.json', 'docs/SLIDE_METHOD_MAP.json', 'docs/SYNCHRONIZATION.md',
                    'docs/REFERENCE_KEY_GUIDE.txt', 'validation/reference_keys_20261113/key_conversion_audit.json']:
        files.update(p for p in ROOT.glob(pattern) if p.is_file())
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    git_status = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True).stdout
    (out / 'repository_status_before_results.txt').write_text(git_status, encoding='utf-8')
    manifest = {'run_id': run_id, 'created_utc': datetime.now(timezone.utc).isoformat(), 'project_root': str(ROOT),
                'repository_revision': revision, 'repository_dirty': bool(git_status), 'python': sys.version,
                'implemented_condition': config['condition_id'], 'configuration': config,
                'configuration_sha256': sha(out / 'condition_configuration.json'), 'commands': commands,
                'file_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)},
                'active_r1': 'REVIEWS.json', 'r1_alias_same_bytes': sha('REVIEWS.json') == sha('REVIEWS_r1_v5_reference_keys.json'),
                'model_runs': 0, 'engineering_model_runs': 0, 'provisional_model_vs_r1': 'unavailable: no predictions',
                'human_comparison': 'not performed: r2 is blank, not an actual submission',
                'docs_sources': ['https://developers.openai.com/api/docs/models/gpt-5.4', 'https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create'],
                'limits': ['configuration selected before outputs', 'existing repository relocation changes preserved', 'no frozen input/review modified', 'no accuracy or reliability estimate']}
    dump(out / 'run_manifest.json', manifest)
    command(['python', 'build_chapter5.py', str(out)], '10_chapter5')
    # Supplement records the build command without rewriting the immutable manifest.
    dump(out / 'commands.json', commands)
    pending = {'execution': {r['case_id']: r['model_execution_blockers'] for r in rows},
               'human': {r['case_id']: {'r1': r['r1_gaps'], 'r2': 'blank template; actual separate submission required', 'adjudication': 'pending actual humans'} for r in rows},
               'next_commands': ['.\\launch_cim.ps1 -Config ' + str(out / 'condition_configuration.json') + ' -RunId ' + run_id,
                                 'python report_results.py ' + str(run_root) + ' --out results/NEW_REPORT_ID/execution_only.json'],
               'adjudication_checklist': ['Preserve actual r1 and distinct r2 first-pass submissions and exposure.', 'Validate both against this freeze.', 'Compare and create a new adjudication template only after r2 submits.', 'Human adjudicator confirms same local scope, source grouping and final evidence/consequences.', 'Review each actual candidate evidence chain; export with --allow-assisted.', 'Generate final condition-specific scoring with matching input hashes.']}
    dump(out / 'pending_work.json', pending)
    text = ('Consequential Interpretation Mismatch (CIM) execution status\nRUN_ID: ' + run_id + '\n'
            '20 proposed/selected; input and selection gates rechecked. See readiness.json for actual case gates.\n'
            'No paid provider attempt and no empirical or engineering model case ran. OPENAI_API_KEY is absent.\n'
            'GPT-5.4 snapshot gpt-5.4-2026-03-05 selected by user; USD100 authorized whole-condition ceiling.\n'
            'Ordinary r1 validation, complete r1/r2 validation, freeze validation, candidate checks and targeted transport tests have saved stdout/stderr/exit codes in logs/.\n'
            'Blank r2 is not a submission. Provisional model-versus-r1 is unavailable until genuine predictions exist.\n'
            'Final accuracy unavailable. Sensitivity undefined without positive adjudicated cases. No independence, lead-time or superiority claim.\n'
            'chapter5_tables.tex and chapter5_results.tex are preparation/execution status only.\n'
            'Use pending_work.json for case-specific human gaps and next commands. Configure OPENAI_API_KEY in the runner process securely; never save it in this repository.\n'
            'Next: ' + pending['next_commands'][0] + '\n'
            'The batch runner prespecifies sorted cases and stops on transport defects; malformed/refused actual replies remain measured outcomes.\n'
            'No automatic retry: this is stricter than the permitted two-attempt/20-extra ceiling. Unknown outcomes require provider reconciliation.\n'
            'Monetary budget uses conservative full reservations, so it may stop before actual charges reach USD100.\n'
            'Transport documentation: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create\n')
    (out / 'RESULTS_README.txt').write_text(text, encoding='utf-8')
    print(json.dumps({'run_id': run_id, 'results': str(out), 'validation_exit_codes': [c['exit_code'] for c in commands],
                      'r1_complete': v1['completed_reviews'], 'r2_complete': v2['completed_reviews'], 'freeze_valid': integrity['valid'],
                      'counts': build(out)}, indent=2))

if __name__ == '__main__': main()
