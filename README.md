# Consequential Interpretation Mismatch (CIM): pilot study

Code, frozen inputs and model outputs for the computational pilot study of *consequential
interpretation mismatch* (CIM) in task-oriented dialogue. A CIM is a point in a dialogue where two
participants may hold different readings of an expression and the difference would change what
they do next.

The pilot applies a staged procedure to 20 dialogue prefixes: 10 from the HCRC Map Task corpus
(`MT01`–`MT10`) and 10 from One Night Ultimate Werewolf games (`WW01`–`WW10`). Each prefix is
labelled `ALIGNED`, `POTENTIAL_MISMATCH` or `UNRESOLVED`.

## Method

Each case is a dialogue prefix cut at a fixed utterance, together with the context available to
both participants. The model receives only four fields per case (task, participants, context
sources, dialogue prefix). It never receives human reviews, later dialogue or expected outcomes.

| Stage | Performed by | Purpose |
|---|---|---|
| F1–F2 discovery | model | identify candidate expressions and the participant pair involved |
| F3 readings | model | enumerate the distinct readings of each expression |
| F4 attribution and check | model, two separate calls | decide which readings each participant's words support, then verify the cited evidence |
| F5 retention | code | keep only readings with verified support |
| F6 task consequences | code | derive what each retained reading implies for the task |
| F7 comparison | code | assign the case label |

Stages F5–F7 are deterministic. A fuller account is in `docs/METHOD_WALKTHROUGH.md`.

## Repository layout

| Path | Contents |
|---|---|
| `pilot.py` | The method: prompts, validation of model output, stages F5–F7 |
| `run_pilot_sync.py` | Runs the cases against the model and records every request and response |
| `report_results.py` | Summarises a run and compares it with a reference register |
| `verify_frozen_inputs.py` | Checks the frozen inputs against their recorded SHA-256 hashes |
| `RUN_CONFIG.json` | Model, decoding settings, prompt revision and budget ceiling |
| `freezes/CIM_INPUTS_20261113_V1/` | The 20 frozen cases, selection register and manifest (the study inputs) |
| `prospective/` | Case construction: source transcripts, maps, selection specifications and build scripts |
| `context/`, `context_reviews/`, `selection_records/`, `review_provenance/` | Records of context verification and case selection referenced by the freeze manifest |
| `REVIEWS.json`, `reviews/reader_2/` | Human reference review (reader 1) and the blank form for a second reader |
| `REVIEW.html`, `REVIEW_GUIDE.html`, `review_ui.py`, `review_tools.py`, `review_key_codec.py`, `web/`, `schemas/`, `wording/` | Review form, its guide, and the tools and schemas behind it |
| `runs/<run>/<case>/` | Model outputs: one request, response and transport record per stage, and `prediction.json` |
| `results/<run>/` | Run configuration, case order and call ledger |
| `tests/` | Unit tests (synthetic data only) |
| `docs/` | Method walkthrough and review field guides |

## Requirements

- Python 3 (developed and tested with 3.14); the study code uses the standard library only.
- An OpenAI API key with access to `gpt-5.4-2026-03-05` (needed only to run the model stages).
- Optional, for the full test suite: `pip install -r requirements-dev.txt`, and Node.js for the
  review-form tests. Tests that need a missing optional tool are skipped.

## Reproducing the study

```
python verify_frozen_inputs.py              # confirm the inputs are intact
python -m unittest discover -s tests -t .   # run the software tests
python run_pilot_sync.py --prepare --all-cases   # fix the configuration and case order; no model calls
python run_pilot_sync.py                    # run, or resume, the model stages
python run_pilot_sync.py --status           # progress and cost
python report_results.py runs/<run> --out summary.json
```

The API key is read from the `OPENAI_API_KEY` environment variable; on Windows,
`set_api_key.ps1` stores it through a hidden prompt. A run can be interrupted and restarted:
completed stages are never sent again, and a call that returns no answer is repeated and logged.
Spending is limited by `total_authorized_ceiling_usd` in `RUN_CONFIG.json`.

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

## Outputs

`runs/<run>/<case>/prediction.json` holds the case label (`prefix_status`), the candidates found,
the readings retained and the reason for the label. For each stage, `<stage>.request.json` is the
exact request and `<stage>.response.txt` the exact model output; the accompanying `.provider.json`,
`.transport.json` and `.response_hash.json` files record the provider's reply, call metadata and
content hash, so that every prediction can be traced to the bytes it was derived from.

## Data sources

- HCRC Map Task corpus: transcripts and maps for ten dialogues, with source revisions and hashes in
  `prospective/provenance/maptask_sources.json` and `prospective/source_maps/provenance.json`.
- Werewolf Among Us (One Night Ultimate Werewolf transcripts): ten games, with source revisions and
  hashes in `prospective/provenance/werewolf_sources.json`.

Both corpora remain subject to their original licences.

## Scope and limitations

- This is a feasibility pilot. No adjudicated reference labels exist, so accuracy, recall and
  false-alarm rates are not reported; comparison with reader 1 is provisional agreement with a
  single assisted reviewer.
- The 20 cases are drawn from 14 source recordings and are not independent samples.
- `UNRESOLVED` is a valid outcome of the procedure, not a failure and not a negative finding.
- Each case was run once; variability across repeated runs was not measured.
