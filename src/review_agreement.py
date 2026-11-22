"""Agreement between two reviewers' label files exported from the reviewer form.

    python src/review_agreement.py data/reviews/labels/setA_reviewer_1.csv data/reviews/labels/setA_reviewer_2.csv

Each file has one row per case with the columns case_id and formal_label.
Prints the number of agreeing cases, Cohen's kappa and the cross-table;
--out writes the same figures and the list of cases needing adjudication as JSON.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

LABELS = ['potential_consequential_mismatch', 'aligned_or_consequence_equivalent', 'unresolved']


def read_labels(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        labels = {row['case_id']: row['formal_label'] for row in csv.DictReader(stream)}
    unknown = sorted(set(labels.values()) - set(LABELS))
    if unknown:
        raise ValueError(f'{path}: unknown label(s) {unknown}')
    return labels


def agreement(first, second):
    if set(first) != set(second):
        raise ValueError('The two files do not cover the same cases.')
    cases = sorted(first)
    total = len(cases)
    agreed = [c for c in cases if first[c] == second[c]]
    observed = len(agreed) / total
    count_1, count_2 = Counter(first.values()), Counter(second.values())
    expected = sum(count_1[label] * count_2[label] for label in LABELS) / total ** 2
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)
    table = {a: {b: sum(first[c] == a and second[c] == b for c in cases) for b in LABELS} for a in LABELS}
    return {'cases': total, 'agreeing_cases': len(agreed), 'observed_agreement': round(observed, 3),
            'chance_agreement': round(expected, 3), 'cohen_kappa': None if kappa is None else round(kappa, 3),
            'cross_table_rows_first_columns_second': table,
            'agreed_labels': {c: first[c] for c in agreed},
            'needs_adjudication': {c: [first[c], second[c]] for c in cases if first[c] != second[c]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('first')
    parser.add_argument('second')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = agreement(read_labels(args.first), read_labels(args.second))
    result = {'first': Path(args.first).name, 'second': Path(args.second).name, **result}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'{result["agreeing_cases"]} of {result["cases"]} cases agree; Cohen\'s kappa {result["cohen_kappa"]}')
    for label in LABELS:
        print(f'  {label:36}', *[f'{result["cross_table_rows_first_columns_second"][label][b]:3}' for b in LABELS])
    print('Needs adjudication:', ', '.join(result['needs_adjudication']) or 'none')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
