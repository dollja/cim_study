"""Build the adjudication form for the Set A cases on which the two reviewers differ.

    python src/build_adjudication_form.py

The form is the Set A reviewer form with three changes: it holds only the cases that need
adjudication, it shows the two earlier answers and their reasons under the conversation
(without names, in an order fixed by SEED), and it exports to its own file. The instructions,
the answer options and the case material are those of the reviewer form, unchanged.

Writes data/reviews/forms/adjudication_setA.html and data/reviews/labels/setA_adjudication_key.csv
(which earlier review is shown as X and which as Y; not for the adjudicator).
"""
from __future__ import annotations
import csv
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMS = ROOT / 'data/reviews/forms'
LABELS = ROOT / 'data/reviews/labels'
SOURCE_FORM = FORMS / 'reviewer_interface.html'
REVIEWS = ('setA_reviewer_1.csv', 'setA_reviewer_2.csv')
SEED = 20261123

NOTE = ('<p><strong>Adjudication.</strong> Two reviewers have already judged these {n} cases and gave '
        'different answers. Their answers and reasons are shown below each conversation as Review X and '
        'Review Y, without names and in no fixed order. Read the conversation first and make your own '
        'judgment; you may agree with either review or with neither.</p>')

EARLIER = '''
    <div class="card">
      <h2 style="margin:0 0 12px 0;font-size:15px;">Earlier reviews of this case</h2>
      ${c.reviews.map(r => `<div class="focus-box" style="margin-top:8px;">
        <div><strong>${escapeHtml(r.tag)}:</strong> ${escapeHtml(r.choice_text)}</div>
        <div style="margin-top:4px;white-space:pre-wrap;">${escapeHtml(r.support)}</div>
      </div>`).join("")}
    </div>
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected exactly one occurrence of {old[:60]!r}; found {text.count(old)}.')
    return text.replace(old, new)


def read_reviews(name):
    with (LABELS / name).open(encoding='utf-8-sig', newline='') as stream:
        return {row['case_id']: row for row in csv.DictReader(stream)}


def build():
    page = SOURCE_FORM.read_text(encoding='utf-8')
    match = re.search(r'const CASES = (\[.*?\]);[ \t]*\r?\n', page, re.S)
    if not match:
        raise ValueError('The reviewer form does not contain the expected case list.')
    cases = json.loads(match.group(1))
    first, second = (read_reviews(name) for name in REVIEWS)
    rng = random.Random(SEED)
    kept, key = [], []
    for case in cases:
        cid = case['case_id']
        if first[cid]['formal_label'] == second[cid]['formal_label']:
            continue
        shown = [(REVIEWS[0], first[cid]), (REVIEWS[1], second[cid])]
        rng.shuffle(shown)
        case = dict(case)
        case['reviews'] = [{'tag': 'Review ' + tag, 'choice_text': row['choice_text'], 'support': row['supporting_evidence']}
                           for tag, (_, row) in zip('XY', shown)]
        kept.append(case)
        key.append({'case_id': cid, 'review_x': shown[0][0], 'review_y': shown[1][0]})
    n = len(kept)

    page = page[:match.start(1)] + json.dumps(kept, ensure_ascii=False) + page[match.end(1):]
    page = replace_once(page, 'const STORAGE_KEY = "pilot_blind_review_v2";', 'const STORAGE_KEY = "pilot_adjudication_setA_v1";')
    page = replace_once(page, '<title>Blind Pilot Review Interface (20 Cases)</title>',
                        f'<title>Pilot Adjudication Interface ({n} Cases)</title>')
    page = replace_once(page, '<h1>Case Review</h1>', '<h1>Case Adjudication</h1>')
    page = replace_once(page, '0 / 20 completed', f'0 / {n} completed')
    page = replace_once(page, 'You will review 20 short cases', f'You will review {n} short cases')
    page = replace_once(page, '</summary>\n', '</summary>\n        ' + NOTE.format(n=n) + '\n') if '</summary>\n' in page \
        else replace_once(page, '</summary>\r\n', '</summary>\r\n        ' + NOTE.format(n=n) + '\r\n')
    question_card = '    <div class="card">\n      <h2 style="margin:0 0 4px 0;font-size:15.5px;">Based on the conversation so far'
    if question_card not in page:
        question_card = question_card.replace('\n', '\r\n')
    page = replace_once(page, question_card, EARLIER.strip('\n') + '\n\n' + question_card)
    page = replace_once(page, 'a.download = "reviewer_labels.csv";', 'a.download = "adjudication_labels_setA.csv";')

    (FORMS / 'adjudication_setA.html').write_text(page, encoding='utf-8', newline='')
    with (LABELS / 'setA_adjudication_key.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['case_id', 'review_x', 'review_y'])
        writer.writeheader()
        writer.writerows(key)
    return kept, key


if __name__ == '__main__':
    kept, key = build()
    print(f'{len(kept)} cases: ' + ', '.join(c['case_id'] for c in kept))
