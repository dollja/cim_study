"""Check a named input freeze without making model calls or certifying review labels.

Run from the project root: python verify_frozen_inputs.py
Use --out with a new filename to preserve a machine-readable validation record.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

from pilot import check_view, digest, read, write_new

ROOT = Path(__file__).resolve().parent
DEFAULT_FREEZE = ROOT / 'freezes/CIM_INPUTS_20261113_V1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(freeze=DEFAULT_FREEZE):
    freeze = Path(freeze).resolve()
    manifest = read(freeze / 'manifest.json')
    errors, cases = [], {}
    checked = 0
    for name, expected in manifest['hashes'].items():
        path = (freeze / name).resolve()
        if not path.is_relative_to(freeze):
            errors.append('Manifest path escapes the freeze: ' + name)
        elif not path.is_file() or sha(path) != expected:
            errors.append('Frozen file missing or changed: ' + name)
        else:
            checked += 1
    for name, expected in manifest.get('provenance_hashes', {}).items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or sha(path) != expected:
            errors.append('Provenance record missing or changed: ' + name)
    with (freeze / 'pilot_selection.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    selected = {r['sample_id']: r for r in rows if r['selected'].lower() == 'true'}
    if len({r['sample_id'] for r in rows}) != len(rows):
        errors.append('Duplicate selection register entries.')
    if set(selected) != set(manifest['observer_files']):
        errors.append('Selected cases differ from the frozen observer manifest.')
    for cid, record in manifest['observer_files'].items():
        case_errors = []
        try:
            path = freeze / record['file']
            view = check_view(read(path))
            wrapper = read(freeze / 'prospective/observer_cases' / (cid + '.json'))
            curator = read(freeze / 'prospective/curator_cases' / (cid + '.json'))
            if sha(path) != record['raw_sha256'] or digest(view) != record['canonical_sha256']:
                case_errors.append('Raw or canonical input hash differs.')
            if wrapper['observer_input'] != view or curator['observer_input'] != view:
                case_errors.append('Observer, wrapper and curator copies differ.')
            if wrapper.get('sample_id') != cid or curator.get('sample_id') != cid:
                case_errors.append('Case identity differs.')
            if wrapper.get('study_role') != 'pilot' or curator.get('study_role') != 'pilot':
                case_errors.append('Current accepted case role must be pilot.')
            if cid not in selected:
                case_errors.append('Case is not selected.')
            if selected.get(cid, {}).get('cutoff_id') != view['dialogue_prefix'][-1]['utterance_id']:
                case_errors.append('Selection cutoff differs from the retained prefix.')
        except (KeyError, TypeError, ValueError, OSError) as exc:
            case_errors.append(str(exc))
        cases[cid] = {'input_and_selection_ready': not case_errors, 'errors': case_errors}
        errors.extend(cid + ': ' + message for message in case_errors)
    return {
        'record_type': 'frozen_input_validation_not_model_results',
        'freeze_id': manifest['freeze_id'], 'valid': not errors,
        'checked_frozen_file_hashes': checked, 'case_count': len(cases),
        'selected_count': len(selected),
        'input_and_selection_ready_cases': sum(c['input_and_selection_ready'] for c in cases.values()),
        'context_verification_basis': manifest['verification_basis'],
        'errors': errors, 'cases': cases,
        'actual_model_calls': 0,
        'limits': 'Confirms recorded inputs, selection, verification declarations and file integrity. Does not authenticate human review, establish participant support, configure a model, or produce predictions.'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', type=Path, default=DEFAULT_FREEZE)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = verify(args.freeze)
    if args.out:
        write_new(args.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
