# Consequential Interpretation Mismatch (CIM) — pilot study

Computational pilot for the thesis chapter on detecting *consequential interpretation mismatches*
in task dialogue: points where two participants may hold different readings of an expression, and
the difference would change what they do next.

**Status, 16 November 2026**

| | |
|---|---|
| Cases selected and frozen | 20 (10 MapTask route dialogues `MT01–MT10`, 10 One Night Ultimate Werewolf games `WW01–WW10`) |
| Model | `gpt-5.4-2026-03-05`, medium reasoning, prompts `cim-current-pilot-0.5` |
| Cases with a model prediction | 2 of 20 (`MT04`, `MT07`, both `UNRESOLVED`) |
| Cases still to run | 18 |
| Human reference | one assisted reviewer (r1), 14 of 20 records complete; no second reader or adjudication yet |
| What can be claimed | feasibility and per-case model output; **not** accuracy, recall or reliability |

The remaining 18 cases have not been run because the machine used for the study had an unreliable
network connection; the method itself is unchanged and the two completed cases ran end to end.

## How the method works

Each case is a dialogue prefix cut at a fixed point, plus the context both participants can see.
The model is called once per stage; everything after stage F4 is deterministic code.

| Stage | Done by | What it does |
|---|---|---|
| F1–F2 discovery | model | finds candidate expressions and the participant pair involved |
| F3 readings | model | lists the distinct meanings each expression could have |
| F4 attribution + check | model, twice | decides which readings each participant's words support, then re-checks the evidence in a separate call |
| F5 retention | code | keeps only readings with verified support |
| F6 task consequences | code | works out what each retained reading implies for the task |
| F7 comparison | code | labels the case `ALIGNED`, `POTENTIAL_MISMATCH` or `UNRESOLVED` |

The model only ever sees the four observer fields of a case (task, participants, context sources,
dialogue prefix). It never sees human reviews, later dialogue or expected outcomes.

## Where things are

| Path | Contents |
|---|---|
| `pilot.py` | The method: prompts, validation of model output, and stages F5–F7 |
| `run_pilot_sync.py` | Runs the cases against the model and saves every request and response |
| `report_results.py` | Summarises saved runs and compares them with reviewed references |
| `verify_frozen_inputs.py` | Checks that the frozen inputs are byte-identical to what was selected |
| `freezes/CIM_INPUTS_20261113_V1/` | The 20 frozen cases and their manifest |
| `REVIEWS.json`, `REVIEW.html` | The active human review (r1) and the form used to edit it |
| `runs/<run>/<case>/` | Per-case evidence: each stage's request, the model's exact reply, and `prediction.json` |
| `results/<run>/` | Per-run configuration and the ledger of calls |
| `tests/` | Software tests; these use synthetic data and are not study results |
| `docs/` | Field guides and notes from the 13 November review package |

## Reading a result

Open `runs/<run>/<case>/prediction.json`. `prefix_status` is the label; the same file lists the
candidates found, the readings kept, and the reason for the label. For any stage,
`<stage>.request.json` is exactly what the model was sent and `<stage>.response.txt` is exactly
what it returned.

## Running it

```
python verify_frozen_inputs.py        # confirm the inputs are intact
python run_pilot_sync.py --prepare    # fix the case list; sends nothing
python run_pilot_sync.py              # run or resume
python run_pilot_sync.py --status     # progress and cost so far
python -m unittest discover -s tests -t .
```

The runner needs an OpenAI API key in the `OPENAI_API_KEY` environment variable
(`set_api_key.ps1` stores one through a hidden prompt). It can be stopped and restarted at any
point; completed stages are never re-sent. A call that returns nothing is sent again and logged.
Spending is capped by `total_authorized_ceiling_usd` in `RUN_CONFIG.json`.

## Limits to keep in mind

- No adjudicated references exist, so no accuracy, recall or false-alarm figure can be reported.
  Comparison with r1 is provisional agreement with one assisted reviewer.
- r1 so far contains no `POTENTIAL_MISMATCH` cases, so mismatch recall is undefined.
- The 20 cases come from 14 source recordings and are not 20 independent samples.
- `UNRESOLVED` is a valid outcome, not a failure and not a negative.
- Earlier development runs (prompt revisions 0.3–0.4 and transport testing) are not part of this
  repository. Their cost is carried in `results/prior_spend.json` so the budget ceiling still counts it.
