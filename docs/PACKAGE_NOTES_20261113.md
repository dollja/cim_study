# Consequential Interpretation Mismatch (CIM) — cim_study

**All 20 episodes, including MT07, are now accepted for this pilot. The 30 context-adapter records are marked verified on the user's confirmation of the supplied source facts and game rules.** This is a disclosed **assisted-development** condition; no blind independent context review is claimed. These dataset gates permit model execution without waiting for reader 2 or final adjudication.

Extract **`cim_study.zip`** and open the **`cim_study`** folder. Open `REVIEW.html` and import `REVIEWS.json` to continue reviewing. The active file is identical to `REVIEWS_r1_v5_reference_keys.json`. It uses the requested reference-style paths, including `subtask_hypotheses[].description`, `focus.quote`, `participant_interpretations`, `consequence_analysis`, `rationale` and `selection_reason`. The original form captions and layout remain unchanged. V4 is preserved with the same frozen inputs; older v2/v3 retain their earlier bindings. All are versions of the same r1 reader.

The inputs are frozen at `freezes/CIM_INPUTS_20261113_V1`. The active r1 file has **14 mechanically complete records and six unfinished records**. A model/provider configuration and genuine transport are still needed; this package update performed no empirical model run. Second-reader comparison and adjudication are separate later steps.

The package remains synchronized with the **20-slide Integrated Early Warning deck dated 2026-11-06**, including notes. Method version: `cim-current-pilot-0.3`; review schema: `1.0`; active review format: `CIM_REFERENCE_KEYS_V1`. This repack changes review representation, not the frozen observer inputs or prediction procedure. Accepting these 20 current candidates does not establish recovery of an earlier historical selection, independent observations or adjudicated labels.

Run `python verify_frozen_inputs.py` to check the delivered freeze before model execution.

## Current files and next action

| File | Use |
|---|---|
| `REVIEWS.json` / `REVIEWS_r1_v5_reference_keys.json` | Active r1 review in the requested reference-key format. |
| `REVIEWS_r1_v4_context_confirmed.json` | Preserved form-label version with the same judgments and frozen input binding. |
| `REVIEWS_r1_v2.json` / `REVIEWS_r1_v3_plain_language.json` | Historical r1 versions; use the archived pre-confirmation observers for their original bindings. |
| `REVIEW.html` | Original form; imports all three review formats and downloads the new reference-key format. |
| `docs/REFERENCE_KEY_GUIDE.txt` | Current paths, their meaning, and a partial MT10 example. |
| `schemas/review_key_map.json` / `docs/FORM_FIELD_MAP.txt` | Existing form-label/internal-name crosswalk; use the new guide for the v5 outer structure. |
| `schemas/reviews.schema.json` | Primary schema for the new reference-key reviews. |
| `schemas/reviews_form_labels.schema.json` / `schemas/reviews_technical.schema.json` | Preserved schemas for the previous form-label and technical encodings. |
| `validation/reference_keys_20261113/key_conversion_audit.json` | Conversion and preservation checks; these are not new human judgments or model results. |
| `CURRENT_READINESS.json` / `CURRENT_READINESS.csv` | Per-case completion gaps, context checks and selection state. These are preparation records, not model results. |
| `CODEX_RUN_PROMPT.txt` | Complete prompt to give Codex for transport, bounded model runs, comparisons and Chapter 5 outputs. |
| `docs/RUN_AND_RESULTS_GUIDE.txt` | Short workflow and reporting boundaries. |
| `context_reviews/CONTEXT_REVIEW_20261113.json` | Records the user's context confirmation and its exposure limits. |
| `selection_records/ACCEPTED_SELECTION_20261113.json` | Records acceptance of all 20 episodes, including MT07. |
| `freezes/CIM_INPUTS_20261113_V1/manifest.json` | Identifies the frozen inputs and selection register. |
| `review_provenance/INPUT_TRANSITION_20261113.json` | Old/new input hashes, status-only equivalence and the separate MT10 update. |
| `validation/selection_context_20261113/` | Freeze and candidate validation records; these are not model results. |

Extract into a new directory. Give Codex that directory and the complete text of `CODEX_RUN_PROMPT.txt`. Codex should verify the available local state, execute what its tools and verified evidence permit, and leave a precise record of any remaining human decisions. Model execution and human adjudication have separate prerequisites; a missing second review does not by itself prevent an otherwise eligible model run.

### MT10: confirmed below-start comparison

MT10 retains `"Review judgment": "ALIGNED"` and `"Could uncertainty change the conclusion?": false`. Both Route consequences now use **`m3_start`**, the existing shared START identifier in the confirmed map inventories, and its review status is `reviewed`. The giver explicitly says *beneath the start* at `.041`; the follower says *under the start* at `.043`. Those utterances support the participants' narrow current below-start relation. The final *yeah* is not the sole evidence.

This update resolves the former null-anchor consistency error without changing the task question or inventing a map entity. It does not establish agreement about the full route. Because the exchange follows clarification, it cannot demonstrate an earlier warning. The substantive consequence/prose update is recorded separately from the administrative input-hash transition.

### Remaining r1 entries

| Cases | Recorded work still needed |
|---|---|
| MT01, MT02, MT04, WW08 | Finish the review and update its status when actually complete. |
| MT07 | Check the interpretation evidence. Its inclusion is now confirmed; `Evidence checked?` remains false. |
| WW03 | Confirm the current content after checking it. |

All 20 may proceed to model execution once the runtime is configured. Only valid completed references can enter the provisional numerical model-versus-r1 comparison. Final accuracy still requires actual second-reader review and adjudication.

## Requested review paths, original form fields

The new format uses the requested names while preserving the current review content:

| New path | Existing meaning |
|---|---|
| `subtask_hypotheses[0].description` | The single local task question. |
| `focus.utterance_id`, `focus.quote`, optional `focus.speaker` | The first saved selected expression and its source. |
| `focus.additional_quotes[]` | The remaining selected expressions, preserved in order. |
| `focus.selected_utterance_ids` | Every selected turn ID; none is discarded. |
| `focus.why_selected` | A separate reason for choosing this focus; currently `null`. |
| `participant_interpretations` | The existing reading array, including each reading's support code and evidence. |
| `consequence_analysis` | The complete existing task-consequence object and canonical consequence sets. |
| `rationale` | Prefix-only justification for the judgment. |
| `selection_reason` | The reason for including or excluding the episode. |

The remaining fields retain readable names such as `Reviewer`, `Review judgment`, `Could uncertainty change the conclusion?` and `Reviewer and exposure`. Nested interpretation and consequence fields retain their existing content. The current human-review workflow handles one task question: it does not implement multiple-hypothesis evaluation by allowing additional array entries.

`focus.why_selected` is a new optional JSON-only field, not a copy of either rationale. It remains null until a reviewer supplies that separate reason; no new HTML control was added. Optional `focus.quote_metadata` preserves extra properties of the primary quote when present. All 20 reviews retain their two selected turn IDs and two quotes. A `possible` reading remains possible, never silently converted to supported.

`REVIEW.html` imports new reference keys, previous form-label keys and technical keys, and exports the reference-key format. The same codec normalizes all three before validation, comparison and canonical hashing. Alias collisions and unsupported ambiguous structures are rejected. Source strings, IDs, codes, Boolean/null values, frozen evidence and the method's decision rules are preserved.

```text
python review_tools.py convert-keys YOUR_REVIEW.json --to reference --out reviews/REFERENCE_REVIEW_NEW.json
python review_tools.py convert-keys YOUR_REVIEW.json --to human --out reviews/FORM_LABEL_REVIEW_NEW.json
python review_tools.py convert-keys YOUR_REVIEW.json --to technical --out reviews/TECHNICAL_REVIEW_NEW.json
```

Use a new output filename. `convert-keys` and CLI `migrate` default to the reference format; `--output-keys human` or `--output-keys technical` selects a migration alternative. Conversion changes representation only and does not certify evidence. `reference` names a field style, not an adjudicated reference. The inherited teaching examples remain unreviewed teaching material, not verified human pilot reviews.

## Start reviewing

1. Extract this ZIP into a **new folder**, such as `C:\github\cim_study`. Keep any more recent local reviews; the attached copies cannot contain edits made after those copies were created.
2. Open `REVIEW.html` in a current desktop browser. Use **Import reviews** to load the root `REVIEWS.json`. The page initially opens with blank records and complete, unmarked prefixes; it never loads the populated review automatically.
3. For a new second reader, import `reviews/reader_2/REVIEWS.json`. That file contains no case-specific suggested interpretation, focus, label or inclusion recommendation. Record the actual reader ID and prior exposure. A reader who has already seen drafts is not made unexposed by using a blank file.
4. Follow `REVIEW_GUIDE.html`: identify the local question; choose two speakers and exact evidence turns; distinguish supported readings from possibilities; describe their task consequences; assess blocking uncertainty; choose the label and explain it from the prefix.
5. To consult alternatives, explicitly load `wording/Tier_S_Wording_Alternatives.json` using the wording control. Open suggestions only when wanted. The editor records exposure and keeps label, verification and inclusion fields unchanged when wording is applied. `wording/REVIEWS_A.json` and `REVIEWS_B.json` are full-file alternative drafts for comparison; use one as a draft, never as an adjudicated reference.
6. **Download `REVIEWS.json` before closing.** The page does not autosave or update the repository. Keep each reader's downloaded file separately and preserve a dated first-pass snapshot before discussing differences or consulting later evidence.

The active r1 file contains 17 `UNRESOLVED` and 3 `ALIGNED` entries. These are human review codes, not model findings. Existing source quotations and declared exposure remain preserved. Preparation history is retained in `review_provenance/R1_PREPARATION_HISTORY.json`; the new version transition is recorded separately. Source-context confirmation does not erase prior draft exposure or certify unfinished interpretations.

## Decision rule

| Code | Enter only when |
|---|---|
| `ALIGNED` | Both participants' supported consequences are the **same single outcome**, with no consequence-changing uncertainty. |
| `POTENTIAL_MISMATCH` | Both supported sets are nonempty, their outcomes are known and **disjoint**, and no blocking uncertainty remains. |
| `UNRESOLVED` | Missing support, unknown facts, competing readings or overlapping non-singleton sets prevent either determination. |
| `null` | You have not rated the case yet. This is not a fourth substantive label. |

The comparison concerns the **same local question, event and phase**. Different wording is not itself a mismatch. Equal sets with several possible consequences do not establish `ALIGNED`. A merely possible reading need not block a decision when its known consequence is already represented and it cannot change the comparison.

## Tier S in practice

Require expressed evidence for each participant's interpretation. A visible landmark establishes availability; it does not show that a speaker adopted it. Bare `okay`, `yeah`, silence or a clarification question do not independently establish adoption. Read the complete permitted prefix: earlier explicit speech or a content-specific endorsement can support a reading even when the final reply is brief. For each proposed reading, inspect the owner of the evidence, reference links, current event/phase and any correction or withdrawal.

Distinguish public role claims from hidden role truth in Werewolf. A report, an attributed belief, a conditional conclusion and an endorsement are different speech acts. Do not add later role revelations, video-derived facts or map bindings to a text-only condition without declaring and freezing a new input condition.

## Validate and compare reviews

Python 3.10+; the primary scripts and tests use the standard library. Run commands from this folder. Each command that writes a review, comparison or reference requires a new output filename.

```text
python review_tools.py validate REVIEWS.json --observer-dir freezes/CIM_INPUTS_20261113_V1/prospective/observer_inputs
python review_tools.py validate REVIEWS.json --observer-dir freezes/CIM_INPUTS_20261113_V1/prospective/observer_inputs --complete
python review_tools.py compare REVIEWS.json reviews/reader_2/REVIEWS.json --observer-dir freezes/CIM_INPUTS_20261113_V1/prospective/observer_inputs --out reviews/comparison_v1.json
```

The review tools accept all three formats. Ordinary validation of active v5 should pass. `--complete` additionally identifies the six unfinished reviews. These checks cover quotes, frozen hashes, controlled values and declared F7 consistency; they cannot independently certify semantic support. Historical v2/v3 files retain their old input bindings: validate them against `history/pre_context_confirmation_20261113/prospective/observer_inputs`, not the new freeze.

To migrate a newer **legacy** local template without replacing it:

```text
python review_tools.py migrate YOUR_CURRENT_TEMPLATE.json --observer-dir freezes/CIM_INPUTS_20261113_V1/prospective/observer_inputs --out reviews/MIGRATED_CURRENT.json
```

An explicit `--wording wording/REVIEWS_A.json` overlay replaces suggested prose fields; preserve your original file and use the result only as a new draft. It does not assign a label, select a case or confirm evidence. An overlay can make an existing determinate label inconsistent with the new pending support records; the CLI refuses that inconsistent output. Keep the original submission and use field-level edits in a separate draft when appropriate. The human-readable output places process flags under `Reviewer and exposure`. Legacy technical names are normalized internally; review content and canonical record/snapshot hashes are preserved through the reversible conversion; raw file bytes change. The original attached human review is retained in `reviews/legacy/`.

## Adjudicate after two real reviews

Compare the local question, pair, focus, interpretations, support and consequences before comparing the label. Two equal codes can reflect different questions. Create a ledger **after** saving the actual reader submissions:

```text
python review_tools.py adjudication-template REVIEWS.json reviews/reader_2/REVIEWS.json --observer-dir freezes/CIM_INPUTS_20261113_V1/prospective/observer_inputs --out reviews/ADJUDICATION_v1.json
```

Resolve differences with a documented rationale. Complete the adjudicator, date, reviewed source grouping, same-scope confirmation and final decision in the ledger. Its hashes bind the adjudication to the two normalized technical review records. A lossless representation change preserves that binding; a substantive review change requires a new ledger. Preserve raw submitted-file hashes separately. For a determinate decision, the ledger needs its own `participant_meanings_with_source_quotes` with supported participant-owned evidence, and `supported_consequences` at the ledger’s top level. Individual reader files keep these sets under `consequence_analysis` → `Supported consequences JSON`; the tools normalize this to the existing internal representation. The adjudication ledger retains its separate technical schema. Record the adjudicator’s resolution without rewriting the two original submissions. The command creates no judgments. Then:

```text
python review_tools.py export-adjudicated REVIEWS.json reviews/reader_2/REVIEWS.json --ledger reviews/ADJUDICATION_v1.json --observer-dir freezes/CIM_INPUTS_20261113_V1/prospective/observer_inputs --out reviews/ADJUDICATED_v1.json --allow-assisted
```

The current root reader file declares prior assistant-draft exposure, so any reference based on it belongs to `assisted_development`. The explicit option retains that classification; it does not waive evidence or completion checks. The default export requires independently submitted, unexposed first-pass judgments. Later assistance must be recorded and cannot retroactively erase exposure or alter the preserved first-pass judgment. The exporter refuses pending or incomplete adjudications.

`evidence_review` in the final ledger concerns an **actual model candidate's evidence chain**, keyed by that candidate ID. It is separate from `Evidence checked?` in a human review. Keep it empty until such a candidate exists and its chain has actually been reviewed.

## Confirmed context, selection and frozen inputs

The user confirmed checking the supplied source context facts and game rules and explicitly selected all 20 cases. The confirmation is recorded under `context_reviews/`; acceptance is under `selection_records/`. Context provenance stays outside model-visible inputs. This supports the disclosed assisted pilot. An unexposed map reader is needed only if a separate independent context-review condition is claimed; it is not an additional execution requirement for this condition.

The observer transition changes only each adapter's `review_status` from `draft` to `verified`. Existing facts, text, entity IDs and correspondence values are unchanged. The selection register records all 20 as selected, and observer wrappers/curator records use `study_role: "pilot"`. The accepted set remains ten MapTask dialogues sharing four map pairs and ten Werewolf transcript records; preserve source dependence and possible shared-session uncertainty.

The complete snapshot is `freezes/CIM_INPUTS_20261113_V1`, with its own selection register and manifest. Old observers and reviews are preserved under `history/pre_context_confirmation_20261113`. Active r1 was explicitly rebound to the new input version using the recorded status-only evidence-equivalence check and per-case old/new raw-file and canonical hashes. This carries forward existing judgments without claiming a fresh human review. MT10's separate anchored-consequence update is disclosed in the same transition record. Original exposure and first-pass history remain unchanged.

```text
python prospective/validate_candidates.py --root freezes/CIM_INPUTS_20261113_V1/prospective --out validation/frozen_NEW.json
```

Use a new output filename. Do not use `--baseline` on this selected/verified version; that option intentionally checks the old draft state. Keep observer inputs identical across the frozen standalone file, wrapper and curator copy. Future changes to actual evidence need a new freeze and review of affected judgments; status-only equivalence cannot justify silently carrying judgments across changed facts. Raw observer-file hashes and canonical observer hashes are both preserved in the transition record.

## Run the method

The implemented harness is the staged strict-evidence condition: F1/F2 discovery, F3 candidate readings, separate participant F4 attribution and support checking, then F5 retention, F6 bounded task computation and F7 comparison. One discovered candidate with one hypothesis uses six model requests. Logical stage count is not model-call count.

The context and selection gates are complete. Next, make `runs/RUN_ID/CASE_ID`, copy `RUN_CONFIG.example.json` there as `run_configuration.json`, and enter the actual model/provider and settings. A genuine API or local-model transport must still be built or connected. The underlying command is:

```text
python pilot.py freezes/CIM_INPUTS_20261113_V1/prospective/observer_cases/CASE_ID.json runs/RUN_ID/CASE_ID --model-id EXACT_MODEL_ID --origin external_model
```

The command writes the next request. Submit only its system/user messages to the declared model in an isolated request, save the untouched reply under the requested `.response.txt` filename and repeat the command. No API connection is built in. Preserve raw failures and provider metadata; duplicate-key or malformed JSON becomes `PROCESSING_FAILURE`, which is separate from `UNRESOLVED`. Use a new run directory for changed code, prompt, configuration or evidence.

The Codex prompt first runs one eligible real smoke case, then the remaining selected cases. It caps each case at 46 distinct stage calls and the full 20 at 920, with at most 20 additional transient transport retries (940 total attempts). Returned malformed or unfavorable results are preserved rather than retried for a better answer.

Only the four observer fields and prior model-stage outputs enter this pipeline. Never supply `REVIEWS.json`, wording, selection specifications, curator drafts, suffixes or reference labels as model input. F2 must discover expressions from the full unmarked prefix, not receive the human focus.

```text
python report_results.py runs/RUN_ID --references reviews/ADJUDICATED_v1.json --out results/pilot_v1.json
```

The report separates independent, assisted and unspecified legacy references. Use the condition-specific counts; combined totals are not blind-review findings. A recorded `external_model` origin is an operator declaration, not independently verified provider execution. Only eligible actual model outputs and adjudicated references support performance claims. New reference exports retain both the raw input-file hash and the same canonical observer hash used by model runs. The reporter requires a matching observer hash; an older unbound reference cannot establish that prediction and reference used the same evidence.

## Software checks and scope

```text
python -m unittest discover -s tests -v
python replay_slides.py --out results/constructed_replay_NEW.json
python prospective/replay_prospective.py --out results/supplied_record_replays_NEW.json
```

Fresh verification is recorded under `validation/`; older evidence under `cim_codex_handoff/` and the older logs/validation summaries under `results/` is explicitly archived. Both replay commands use supplied interpretation/support records, not a model. Their labels demonstrate code execution only. The three legacy `q1ec2` teaching cases are not independent and two overlap.

Implemented task adapters cover symbolic map anchors/routes/checkpoints, scheduling diagnostics, explicit targets and bounded reported/conditional holder exchanges. Full route geometry, general role-of-person or information-access reasoning, all three comparison arms, successive-prefix warning timing, model API transport and automatic adjudication are not implemented. The action/requirement extension on slide 13 has separate `Met`, `Not-Met` and `Cannot-Determine` outputs and is not part of the primary F7 label.

See `CHAPTERS_3_4_WALKTHROUGH.md`, `docs/SLIDE_METHOD_MAP.json` and `docs/SYNCHRONIZATION.md` for the precise slide mapping, input identities and boundaries. The newly supplied attachments do not include the complete Chapter 3–4 PDF, so this update does not claim a fresh verification of that full document. Nothing was pushed to an external repository.
