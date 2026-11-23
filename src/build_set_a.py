"""Build the Set A input sets from the case package prepared for two-reviewer annotation.

    python src/build_set_a.py <folder holding pilot_cases.jsonl and paired_controls.jsonl>

Writes two input sets under data/inputs/:

  CIM_INPUTS_20261121_SETA_V1            the cases of the package
  CIM_INPUTS_20261121_SETA_CONTROLS_V1   its paired controls (each a case extended by two responses)

Only the task description, participants, context and the dialogue up to the cutoff go into
observer_input. The package's proposed labels and the turns after the cutoff are kept in
curator_cases and are never sent to the model.

Context follows the first input set (CIM_INPUTS_20261113_V1):
  Map Task  the verified landmark lists of that set, reused unchanged. A case whose map pair has
            no verified list is left out and reported.
            Lists confirmed later are read from data/context/.
  Werewolf  the same task description and the same standard role list. The instructions text is
            what a recorded game-audio speaker says in the prefix; where there is none, the text
            states only that and the role list.
"""
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pilot

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'data/inputs'
FIRST = INPUTS / 'CIM_INPUTS_20261113_V1/prospective/observer_cases'
PACKAGE_SHA256 = '1ea91003ff17c0e99ca5040491cc456a70c1ebd632638522f87f90577015f859'
SETS = {'CIM_INPUTS_20261121_SETA_V1': ('pilot_cases.jsonl', 'case_id'),
        'CIM_INPUTS_20261121_SETA_CONTROLS_V1': ('paired_controls.jsonl', 'control_id')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def first_set_context():
    """Landmark lists, task descriptions and the role list of the first input set."""
    inventories, tasks, roles = {}, {}, None
    for path in sorted(FIRST.glob('*.json')):
        view = pilot.read(path)['observer_input']
        for source in view['context_sources']:
            kind = source['adapter']['kind']
            tasks[kind] = view['overall_task']
            if kind == 'map_inventory':
                inventories[source['source_id']] = source
            elif roles is None:
                roles = source['adapter']['roles']
            elif roles != source['adapter']['roles']:
                raise ValueError('The first input set does not use one role list.')
    for path in sorted((ROOT / 'data/context').glob('*.json')):  # landmark lists confirmed after the first set
        for source in pilot.read(path)['context_sources']:
            if source['adapter'].get('review_status') == 'verified':
                inventories[source['source_id']] = source
    return inventories, tasks, roles


def map_view(case, inventories, task):
    pair = case['group_id']
    context = [inventories.get(f'{pair}_{role}_inventory') for role in ('giver', 'follower')]
    if None in context:
        return None, None, f'no verified landmark list for map pair {pair}'
    turns = case['observer_input']['dialogue_prefix']
    prefix = [{'utterance_id': f'{case["source"]}.ln.{t["ln"]:03}', 'speaker': t['speaker'], 'text': t['text']}
              for t in turns]
    view = {'overall_task': task,
            'participants': [{'participant_id': 'giver', 'known_role': 'giver'},
                             {'participant_id': 'follower', 'known_role': 'follower'}],
            'context_sources': context, 'dialogue_prefix': prefix}
    return view, f'{case["source"]}_l{turns[-1]["ln"]:03}', None


def game_view(case, slot, roles, task):
    turns = case['observer_input']['dialogue_prefix']
    players = case['observer_input']['admissible_facts']['players']
    audio = sorted({t['speaker'] for t in turns} - set(players))
    prefix = [{'utterance_id': f'{slot}.turn.{t["turn"]:03}', 'speaker': t['speaker'], 'text': t['utterance']}
              for t in turns]
    spoken = [t['utterance'] for t in turns if t['speaker'] in audio]
    text = ' '.join(spoken) if spoken else ('No recorded game instructions precede this discussion. '
                                           'Roles that may be in play: ' + ', '.join(roles) + '.')
    view = {'overall_task': task,
            'participants': [{'participant_id': p, 'known_role': None} for p in players]
                            + [{'participant_id': p, 'known_role': 'recorded_audio_not_player'} for p in audio],
            'context_sources': [{'source_id': f'{slot}_public_instructions', 'text': text,
                                 'accessible_to_participants': players,
                                 'adapter': {'kind': 'game_rules', 'review_status': 'verified', 'roles': roles}}],
            'dialogue_prefix': prefix}
    return view, f't{turns[-1]["turn"]:03}', None


def build(package, name, source_file, id_field, inventories, tasks, roles):
    here = INPUTS / name
    if here.exists():
        raise ValueError(f'{here} exists; move it away before rebuilding.')
    (here / 'source').mkdir(parents=True)
    for extra in {source_file, 'screening_log.csv', 'selection_summary.md'}:
        shutil.copyfile(package / extra, here / 'source' / extra)
    rows, observer_files, left_out = [], {}, {}
    for line in (here / 'source' / source_file).read_text(encoding='utf-8').splitlines():
        case = json.loads(line)
        slot = 'A' + case[id_field].replace('-', '')
        is_map = case['dataset'].startswith('HCRC')
        if is_map:
            view, tail, problem = map_view(case, inventories, tasks['map_inventory'])
        else:
            view, tail, problem = game_view(case, slot, roles, tasks['game_rules'])
        if problem:
            left_out[case[id_field]] = problem
            continue
        cutoff = case.get('cutoff') or case['extended_cutoff']
        unit = 'utt' if is_map else 'turn'
        if max(t[unit] for t in case['observer_input']['dialogue_prefix']) != cutoff['value']:
            raise ValueError(case[id_field] + ': prefix does not end at the cutoff.')
        pilot.check_view(view)
        cid = f'{slot}_{tail}'
        keep = {k: case[k] for k in ('review_annotations', 'later_evidence', 'verification_status', 'parent_case_id',
                                     'original_cutoff', 'extended_cutoff', 'added_responses_count') if k in case}
        files = {'observer_inputs': view,
                 'observer_cases': {'sample_id': cid, 'study_role': 'pilot', 'observer_input': view},
                 'curator_cases': {'sample_id': cid, 'dataset': case['dataset'], 'study_role': 'pilot',
                                   'source': {'package_id': case[id_field], 'source_conversation': case['source'],
                                              'group': case['group_id'], 'cutoff': cutoff},
                                   'observer_input': view, 'package_record_not_sent_to_model': keep}}
        for folder, content in files.items():
            pilot.write_new(here / 'prospective' / folder / (cid + '.json'), content)
        path = here / 'prospective/observer_inputs' / (cid + '.json')
        observer_files[cid] = {'file': f'prospective/observer_inputs/{cid}.json', 'raw_sha256': sha(path),
                               'canonical_sha256': pilot.digest(view)}
        rows.append({'slot_id': slot, 'dataset': 'MapTask/GMMT' if is_map else 'Werewolf Among Us', 'sample_id': cid,
                     'source_conversation': case['source'], 'map_pair_or_game_group': case['group_id'],
                     'cutoff_id': view['dialogue_prefix'][-1]['utterance_id'], 'selected': 'true',
                     'reference_status': 'two_reviews_collected_adjudication_pending'
                     if id_field == 'case_id' else 'paired_control_not_reviewed'})
    with (here / 'pilot_selection.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    hashed = sorted(p for p in here.rglob('*') if p.is_file() and p.name != 'manifest.json')
    pilot.write_new(here / 'manifest.json', {
        'freeze_id': name, 'date': '2026-11-23', 'record_type': 'observer_input_freeze',
        'verification_basis': 'Landmark lists and role list reused unchanged from CIM_INPUTS_20261113_V1; '
                              'm2 landmark lists from data/context (user attestation). Dialogue text taken from the case package; it was compared '
                              'with the source corpora and matched.',
        'accepted_case_count': len(rows), 'canonical_hash_function': 'pilot.digest',
        'source_package': {'file': 'consequential-mismatch-study-handoff.zip', 'sha256': PACKAGE_SHA256},
        'built_by': 'src/build_set_a.py', 'not_built': left_out,
        'hashes': {p.relative_to(here).as_posix(): sha(p) for p in hashed},
        'observer_files': observer_files,
        'model_visibility': 'Only observer_input in generated request messages; curator files, package annotations '
                            'and later evidence must not be sent to the evaluated model.',
        'measured_model_runs': 0})
    print(f'{name}: {len(rows)} built; left out: {left_out or "none"}')


def main(package):
    inventories, tasks, roles = first_set_context()
    for name, (source_file, id_field) in SETS.items():
        build(Path(package), name, source_file, id_field, inventories, tasks, roles)


if __name__ == '__main__':
    main(sys.argv[1])
