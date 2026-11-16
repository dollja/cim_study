"""Audit source integrity and review progress without overwriting archived records.

Default validation permits completed reviews/selections. --baseline additionally checks
the original unselected, unreviewed draft state. Neither mode measures model performance.
"""
import argparse
import copy
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
from pilot import check_view, read, write_new
try:
    from .build_candidates import parse
except ImportError:
    from build_candidates import parse


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(root=ROOT, baseline=False):
    root = Path(root).resolve()
    specs = read(root / 'selection_specs.json')
    expected_slots = {f'{prefix}{i:02}' for prefix in ['MT', 'WW'] for i in range(1, 11)}
    require(len(specs) == 20 and {s['id'] for s in specs} == expected_slots,
            'Expected the 20 MT01–MT10 and WW01–WW10 candidate slots.')
    expected = {f"{s['id']}_{s['source']}_r{s['cutoff']:03}": s for s in specs}
    for directory in ['curator_cases', 'observer_inputs', 'observer_cases']:
        require({p.stem for p in (root / directory).glob('*.json')} == set(expected),
                f'{directory}: case IDs do not match the 20 selection specifications.')
    provenance_rows = [r for name in ['maptask_sources', 'werewolf_sources']
                       for r in read(root / 'provenance' / (name + '.json'))]
    provenance = {r['source_id']: r for r in provenance_rows}
    require(len(provenance_rows) == len(provenance) == 20,
            'Expected 20 distinct transcript provenance entries.')
    require(set(provenance) == {s['source'] for s in specs},
            'Transcript provenance IDs differ from selection source IDs.')

    records = []
    preflight = []
    for sid, spec in sorted(expected.items()):
        record = read(root / 'curator_cases' / (sid + '.json'))
        records.append(record)
        source = record['source']
        require(record['sample_id'] == sid and source['dialogue_id'] == spec['source'],
                sid + ': curator/source ID mismatch.')
        is_game = spec['id'].startswith('WW')
        require(record['dataset'] == ('Werewolf Among Us' if is_game else 'MapTask/GMMT'),
                sid + ': unexpected dataset.')
        declared = provenance[spec['source']]
        require(all(source.get(k) == value for k, value in declared.items()),
                sid + ': curator source differs from pinned provenance.')
        require(source['local_path'] == f"source_transcripts/{spec['source']}.txt",
                sid + ': unexpected local transcript path.')
        data = (root / source['local_path']).read_bytes()
        require(hashlib.sha256(data).hexdigest() == source['sha256'], sid + ': SHA-256 mismatch.')
        require(hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                == source['git_blob_sha1'], sid + ': Git blob hash mismatch.')
        require(len(data) == source['bytes'], sid + ': source byte count mismatch.')
        all_rows, crosswalk = parse(source['dialogue_id'], is_game, root)
        require(read(root / 'crosswalks' / (spec['source'] + '.json')) == crosswalk,
                sid + ': saved source-line crosswalk differs from raw transcript parsing.')
        require(len({x['source_line'] for x in crosswalk['rows']}) == len(all_rows),
                sid + ': duplicated source-line mapping.')

        view = read(root / 'observer_inputs' / (sid + '.json'))
        wrapper = read(root / 'observer_cases' / (sid + '.json'))
        require(set(view) == {'overall_task', 'participants', 'context_sources', 'dialogue_prefix'},
                sid + ': observer input must have exactly four permitted fields.')
        require(view == record['observer_input'] == wrapper['observer_input'],
                sid + ': observer/curator copies have diverged.')
        require(wrapper['sample_id'] == sid and wrapper['study_role'] == record['study_role'],
                sid + ': observer wrapper identity/role differs from curator record.')
        selection = record['selection_metadata']
        n = selection['prefix_utterance_count']
        require(isinstance(n, int) and 2 <= n <= len(all_rows) and n == spec['cutoff']
                and spec['focus'] == n - 1, sid + ': invalid observation boundary.')
        require(view['dialogue_prefix'] == all_rows[:n], sid + ': prefix is not complete to cutoff.')
        require(record['later_evidence']['dialogue'] == all_rows[n:],
                sid + ': suffix differs from the remaining source transcript.')
        focus, response = all_rows[n - 2:n]
        require(selection['focus_utterance_id'] == focus['utterance_id']
                and selection['focal_episode_start_id'] == focus['utterance_id']
                and selection['first_relevant_response_id'] == response['utterance_id']
                and selection['observation_cutoff_id'] == response['utterance_id'],
                sid + ': focus/first-response/cutoff IDs differ from adjacent source rows.')
        require(focus['speaker'] != response['speaker']
                and [focus['speaker'], response['speaker']] == spec['pair'],
                sid + ': focal-pair boundary differs from selection specification.')
        require(selection['prefix_word_count'] == sum(len(t['text'].split()) for t in all_rows[:n]),
                sid + ': prefix word count mismatch.')

        # Validate all nested fields even when an early draft adapter blocks a live run.
        # This temporary copy is discarded; no inventory is marked verified on disk.
        structural = copy.deepcopy(view)
        for context in structural['context_sources']:
            if isinstance(context, dict) and isinstance(context.get('adapter'), dict):
                context['adapter']['review_status'] = 'verified'
        check_view(structural)
        try:
            check_view(view)
        except ValueError as ex:
            require('reviewed/verified' in str(ex), sid + ': ' + str(ex))
            preflight.append({'sample_id': sid, 'status': 'blocked_unverified_context', 'reason': str(ex)})
        else:
            preflight.append({'sample_id': sid, 'status': 'passed_context_preflight'})

        if baseline:
            review = record['annotation_review']
            require(record['manual_annotation'] is None
                    and all(review.get(k) is None for k in ['independent_coder_1', 'independent_coder_2', 'adjudicated_label'])
                    and review['review_status'] == 'unreviewed', sid + ': baseline requires null/unreviewed annotations.')
            require(record['study_role'] == 'prospective_candidate_unselected'
                    and selection['selection_status'] == 'assistant_proposed_awaiting_human_selection'
                    and not any(value is True for key, value in selection.items() if key.startswith('confirmed_as_')),
                    sid + ': baseline requires the original unselected state.')
            require(all(c['adapter']['review_status'] == 'draft' for c in view['context_sources']),
                    sid + ': baseline requires draft context.')

    map_rows = read(root / 'source_maps' / 'provenance.json')
    expected_maps = {f'map{n}{side}.gif' for n in [3, 6, 9, 12] for side in ['g', 'f']}
    require(len(map_rows) == 8 and {r['file'] for r in map_rows} == expected_maps,
            'Map provenance does not contain the eight source maps.')
    for source in map_rows:
        data = (root / 'source_maps' / source['file']).read_bytes()
        require(hashlib.sha256(data).hexdigest() == source['sha256'], source['file'] + ': source map hash mismatch.')

    with (root.parent / 'pilot_selection.csv').open(encoding='utf-8-sig', newline='') as f:
        register = list(csv.DictReader(f))
    require(len(register) == 20 and {r['sample_id'] for r in register} == set(expected),
            'Selection register must contain every candidate exactly once.')
    for row in register:
        spec = expected[row['sample_id']]
        require(row['slot_id'] == spec['id'] and row['source_conversation'] == spec['source']
                and row['cutoff_id'] == f"{spec['source']}.row.{spec['cutoff']:03}",
                'Selection-register source boundary mismatch: ' + row['sample_id'])
        require(row['selected'].lower() in {'true', 'false'}, 'Selection entries must use true or false.')
        if baseline:
            require(row['selected'].lower() == 'false', 'Baseline requires all selection entries to be false.')

    return {
        'validation': 'passed', 'mode': 'baseline' if baseline else 'current_state',
        'prospective_records': len(records), 'source_blob_hashes_matching': len(records),
        'source_map_hashes_matching': len(map_rows),
        'complete_prefix_suffix_reconstructions': len(records),
        'first_response_boundaries_checked': len(records),
        'model_input_objects_without_curator_fields': len(records),
        'context_structural_checks_passed': len(records),
        'context_preflight_passed': sum(p['status'] == 'passed_context_preflight' for p in preflight),
        'unverified_contexts_block_model_run': sum(p['status'] == 'blocked_unverified_context' for p in preflight),
        'selected_declared_in_register': sum(r['selected'].lower() == 'true' for r in register),
        'study_roles_declared': dict(Counter(r['study_role'] for r in records)),
        'annotation_review_statuses_declared': dict(Counter(r['annotation_review']['review_status'] for r in records)),
        'reference_labels_adjudicated_declared': sum(r['annotation_review'].get('adjudicated_label') is not None for r in records),
        'model_run_audit': 'not performed; no inference execution or performance claim follows from this validation',
        'case_context_preflight': preflight,
        'limitations': 'Byte and structure checks do not validate interpretation support, transcription against media, independence, map correspondences or human reference labels. Declared review and selection states are not independently authenticated.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Prospective directory to validate.')
    parser.add_argument('--baseline', action='store_true', help='Require the original untouched draft state.')
    parser.add_argument('--out', type=Path, help='Optional new JSON report path; different existing content is never overwritten.')
    args = parser.parse_args()
    result = validate(args.root, args.baseline)
    if args.out:
        write_new(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
