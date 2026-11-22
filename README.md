# Consequential interpretation mismatch pilot study

Code, input data, human reviews and model outputs for a computational pilot study of
*consequential interpretation mismatch* (CIM) in task-oriented dialogue. A CIM is a point in a
dialogue where two participants hold different readings of what was said, and the difference would
change what they do next.

The study applies a staged procedure to short dialogue prefixes from two corpora, the HCRC Map
Task corpus and One Night Ultimate Werewolf games, and assigns each prefix one of three labels:
potential mismatch, aligned, or unresolved.

## Repository layout

| Path | Contents |
|---|---|
| `src/pilot.py` | The method: prompts, validation of model output, and the rule-based stages |
| `src/run_pilot_sync.py` | Runs the cases against the model and records every request and response |
| `src/verify_frozen_inputs.py` | Checks an input set against its recorded SHA-256 hashes |
| `src/report_results.py` | Summarises a run and scores it against a reference register |
| `src/review_agreement.py` | Agreement between two reviewers' label files |
| `config/RUN_CONFIG.json` | Model, decoding settings, prompt revision and budget ceiling |
| `data/inputs/` | Frozen input sets (cases exactly as given to the model, with manifests) |
| `data/reviews/` | Reviewer forms and the labels collected with them |
| `data/provenance/` | Records of context verification and case selection for the first input set |
| `runs/<run>/<case>/` | Model outputs: one request, response and transport record per stage, and `prediction.json` |
| `results/` | Run configuration, case order, call ledger, cost record and reviewer agreement |
| `tests/` | Unit tests (constructed data only; no model calls) |
| `docs/` | Method description |
| `scripts/` | Helper for storing the API key on Windows |

## Case sets

| Set | Cases | Input set | Reviewer form | Status |
|---|---|---|---|---|
| B | 20 (10 Map Task, 10 Werewolf), each cut at the first response to a focal utterance | `data/inputs/CIM_INPUTS_20261113_V1` | `data/reviews/forms/reviewer_interface_setB.html` | Model run complete; one initial review |
| A | 20 (10 Map Task, 10 Werewolf), balanced across the three labels by the selector, with 8 paired controls | `data/inputs/CIM_INPUTS_20261121_SETA_V1` (8 Map Task cases so far) | `data/reviews/forms/reviewer_interface.html` | Two independent reviews collected; adjudication and model run pending |

`data/README.md` describes the files in each set and where the source data come from.

## Method

Each case is a dialogue prefix cut at a fixed utterance, together with the context each
participant can see (the landmark list of their own map, or the public game instructions). The
model receives four fields per case: task, participants, context sources and dialogue prefix. It
never receives reviewer labels, later dialogue or the point of interest.

| Stage | Performed by | Purpose |
|---|---|---|
| F1–F2 discovery | model | propose up to three candidate points and the two participants involved |
| F3 readings | model | list the plausible readings at each point |
| F4 attribution and check | model, two separate calls | decide which readings each participant's own words support, then recheck the cited evidence |
| F5 retention | code | keep only readings with verified support |
| F6 task consequence | code | derive what each retained reading implies for the task |
| F7 comparison | code | assign the label |

Stages F5–F7 are deterministic. Details are in `docs/METHOD.md`.

## Requirements

- Python 3 (developed and tested with 3.14). The code uses the standard library only.
- An OpenAI API key with access to `gpt-5.4-2026-03-05`, needed only for the model stages.

## Reproducing the study

```
python src/verify_frozen_inputs.py                 # confirm the Set B inputs are intact
python -m unittest discover -s tests -t .          # run the software tests
python src/run_pilot_sync.py --prepare --all-cases # fix configuration and case order; no model calls
python src/run_pilot_sync.py                       # run, or resume, the model stages
python src/run_pilot_sync.py --status              # progress and cost
python src/review_agreement.py data/reviews/labels/setA_reviewer_1.csv data/reviews/labels/setA_reviewer_2.csv
```

Add `--input-set CIM_INPUTS_20261121_SETA_V1` to the runner and
`--freeze data/inputs/CIM_INPUTS_20261121_SETA_V1` to the verifier to work on Set A.

The API key is read from the `OPENAI_API_KEY` environment variable; on Windows,
`scripts/set_api_key.ps1` stores it through a hidden prompt. A run can be interrupted and
restarted: completed stages are never sent again, and a call that returns no answer is repeated
and logged. Spending across all runs is limited by `total_authorized_ceiling_usd` in
`config/RUN_CONFIG.json`.

Model outputs are not deterministic, so a new run reproduces the procedure, not necessarily the
same labels.

## Configuration

| Setting | Value |
|---|---|
| Model | `gpt-5.4-2026-03-05` |
| Reasoning effort | medium |
| Maximum output tokens | 8192 |
| Prompt revision | `cim-current-pilot-0.5` |
| Interface | OpenAI Responses API, one streamed call per stage |

## Results to date

**Set B, model run** (`runs/20261117T032351897500Z_strictS_gpt54_sync_v1`). The procedure returned
*unresolved* for all 20 cases. The initial review labelled 17 unresolved and 3 aligned, so the two
agree on 17 of 20. Across the cases the model tested 136 hypotheses: 134 unresolved, 2 aligned,
none a mismatch. The set contains no case reviewed as a mismatch, so recall cannot be computed.

**Set A, human review** (`results/review_agreement_setA.json`). Two reviewers labelled the 20
cases independently with the same form. They agree on 8 of 20 (Cohen's kappa −0.02) and on no
mismatch case; 12 cases await adjudication. The model has not been run on Set A.

## Outputs

`runs/<run>/<case>/prediction.json` holds the case label (`prefix_status`), the candidates found,
the readings retained and the outcome of each hypothesis. For each stage, `<stage>.request.json`
is the exact request and `<stage>.response.txt` the exact model output; the accompanying
`.provider.json`, `.transport.json` and `.response_hash.json` files record the provider's reply,
call metadata and content hash, so that every prediction can be traced to the bytes it was derived
from. Where a case was evaluated again after a software repair, the earlier record is kept in the
case's `superseded/` folder.

## Scope and limitations

- This is a feasibility pilot. No adjudicated reference labels exist yet, so accuracy, recall and
  false-alarm rates are not reported.
- The Set B points were chosen by judgement with the help of an AI assistant and reviewed by one
  reader who had seen the assistant's drafts. The Set A cases were also selected by judgement, and
  their labels are under review.
- Cases within a set share source recordings and are not independent samples.
- *Unresolved* is a valid outcome of the procedure, not a failure and not a negative finding.
- Each case was run once; variability across repeated runs was not measured.
- Four Set B cases first ended in a processing failure and were evaluated again after a repair to
  the rule-based stage and the runner. Prompts, cases and comparison rules were not changed, and
  the 16 cases completed earlier give identical results under the repaired code.
