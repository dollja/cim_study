# Consequential Interpretation Mismatch (CIM) — pilot review and early-warning method

**Review and model-run handoff updated 2026-11-13. Start with `REVIEW.html` and import `REVIEWS.json`.**
The active file is identical to `REVIEWS_r1_v3_plain_language.json`. `REVIEWS_r1_v2.json` is the earlier wording version of the same reader, r1; it is not a second reader. Both versions include the requested MT10 edit and the streamlined preparation notes.

The package retains its synchronization with the **20-slide Integrated Early Warning deck dated 2026-11-06**, including speaker notes. Method software version: `cim-current-pilot-0.3`; review schema: `1.0`; this review/form handoff revision: `2026-11-13`. No new inspection of the full Chapter 3–4 PDF or new empirical model run is claimed.

The package contains **20 proposed episodes**: ten MapTask dialogues on four map pairs and ten Werewolf transcript records. The saved r1 reviews recommend 19 for inclusion and leave MT07 undecided. The final selection register still contains zero selected cases. Thirteen r1 records pass the current mechanical completeness checks; a second human review and final adjudication are still outstanding. All 20 real-case execution preflights remain blocked by 30 draft context-adapter records.

## Current files and next action

| File | Use |
|---|---|
| `REVIEWS.json` / `REVIEWS_r1_v3_plain_language.json` | Continue the current r1 review; these are identical copies at packaging time. |
| `REVIEWS_r1_v2.json` | Earlier wording version with the same authorized edit; keep as a revision, not as r2. |
| `REVIEW.html` | Offline editor; imports either review version and exports canonical JSON. |
| `schemas/review_fields.json` / `docs/FORM_FIELD_MAP.txt` | Exact mapping for 35 displayed form captions and JSON paths. |
| `CURRENT_READINESS.json` / `CURRENT_READINESS.csv` | Per-case completion gaps, context checks and selection state. These are preparation records, not model results. |
| `CODEX_RUN_PROMPT.txt` | Complete prompt to give Codex for transport, bounded model runs, comparisons and Chapter 5 outputs. |
| `docs/RUN_AND_RESULTS_GUIDE.txt` | Short workflow and reporting boundaries. |
| `review_provenance/` | Historical preparation records and unchanged source snapshots; excluded from model inputs. |

Extract into a new directory. Give Codex that directory and the complete text of `CODEX_RUN_PROMPT.txt`. Codex should verify the available local state, execute what its tools and verified evidence permit, and leave a precise record of any remaining human decisions. Model execution and human adjudication have separate prerequisites; a missing second review does not by itself prevent an otherwise eligible model run.

### MT10: requested change and remaining check

`blocking_uncertainty` is now `false` in both versions. The entered label remains `ALIGNED`. Both saved Route consequences still contain a required START value of `null`, so the implemented decision check continues to expect `UNRESOLVED`. The form now displays that inconsistency without changing the saved judgment. No START identity, context certification or completed review was invented.

The prefix supports both speakers expressing a below-start direction. A verified common START location is still needed for the complete anchored route consequence recorded in this file. Verify and enter that fact with its provenance, or revise the judgment to match what the available evidence supports. A deliberately different relation-only comparison would be a separately defined task question, not an invisible repair.

### Remaining r1 entries

| Cases | Recorded work still needed |
|---|---|
| MT01, MT02, MT04, MT10, WW08 | Finish the review and update its status when actually complete. |
| MT07 | Verify the evidence; decide its inclusion recommendation. |
| WW03 | Confirm the current content after checking it. |
| MT10 | Also resolve the required START argument / saved-label inconsistency above. |

The detailed status is derived from the current files, not from the older preparation labels in `pilot_selection.csv`. The CSV's selection flags remain unchanged. Continue to preserve actual review history when updating its final selection and reference-status fields.

## Start reviewing

1. Extract this ZIP into a **new folder**, such as `C:\github\cim_pilot_updated`. Keep any more recent local reviews; the attached copies cannot contain edits made after those copies were created.
2. Open `REVIEW.html` in a current desktop browser. Use **Import reviews** to load the root `REVIEWS.json`. The page initially opens with blank records and complete, unmarked prefixes; it never loads the populated review automatically.
3. For a new second reader, import `reviews/reader_2/REVIEWS.json`. That file contains no case-specific suggested interpretation, focus, label or inclusion recommendation. Record the actual reader ID and prior exposure. A reader who has already seen drafts is not made unexposed by using a blank file.
4. Follow `REVIEW_GUIDE.html`: identify the local question; choose two speakers and exact evidence turns; distinguish supported readings from possibilities; describe their task consequences; assess blocking uncertainty; choose the label and explain it from the prefix.
5. To consult alternatives, explicitly load `wording/Tier_S_Wording_Alternatives.json` using the wording control. Open suggestions only when wanted. The editor records exposure and keeps label, verification and inclusion fields unchanged when wording is applied. `wording/REVIEWS_A.json` and `REVIEWS_B.json` are full-file alternative drafts for comparison; use one as a draft, never as an adjudicated reference.
6. **Download `REVIEWS.json` before closing.** The page does not autosave or update the repository. Keep each reader's downloaded file separately and preserve a dated first-pass snapshot before discussing differences or consulting later evidence.

Existing progress and all exact source quotations were preserved. The current r1 files contain 17 `UNRESOLVED` and 3 `ALIGNED` entries, with the MT10 consistency issue described above. Repeated preparation paragraphs have moved to `review_provenance/R1_PREPARATION_HISTORY.json`. The previously declared exposure flag and required provenance fields remain accurate. Wordings, completion flags and reference status must not be used to imply an unexposed review history.

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
python review_tools.py validate REVIEWS.json --observer-dir prospective/observer_inputs
python review_tools.py validate REVIEWS.json --observer-dir prospective/observer_inputs --complete
python review_tools.py compare REVIEWS.json reviews/reader_2/REVIEWS.json --observer-dir prospective/observer_inputs --out reviews/comparison_v1.json
```

Ordinary validation permits unfinished work but currently reports the MT10 decision inconsistency. `--complete` additionally reports the outstanding review requirements. All three current r1 file copies pass the JSON schema; this is separate from a passing substantive consistency/completeness check. Source quotations, frozen input hashes, controlled values and declared F7 consistency are checked mechanically; semantic support still requires readers.

To migrate a newer **legacy** local template without replacing it:

```text
python review_tools.py migrate YOUR_CURRENT_TEMPLATE.json --observer-dir prospective/observer_inputs --out reviews/MIGRATED_CURRENT.json
```

An explicit `--wording wording/REVIEWS_A.json` overlay replaces suggested prose fields; preserve your original file and use the result only as a new draft. It does not assign a label, select a case or confirm evidence. An overlay can make an existing determinate label inconsistent with the new pending support records; the CLI refuses that inconsistent output. Keep the original submission and use field-level edits in a separate draft when appropriate. Old process flags move into `review_metadata`; stable substantive keys stay recognizable. The original attached human review is retained in `reviews/legacy/`.

## Adjudicate after two real reviews

Compare the local question, pair, focus, interpretations, support and consequences before comparing the label. Two equal codes can reflect different questions. Create a ledger **after** saving the actual reader submissions:

```text
python review_tools.py adjudication-template REVIEWS.json reviews/reader_2/REVIEWS.json --observer-dir prospective/observer_inputs --out reviews/ADJUDICATION_v1.json
```

Resolve differences with a documented rationale. Complete the adjudicator, date, reviewed source grouping, same-scope confirmation and final decision in the ledger. Its hashes bind the adjudication to the exact two review records; regenerate a new ledger if those submissions change. For a determinate decision, the ledger needs its own `participant_meanings_with_source_quotes` with supported participant-owned evidence, and `supported_consequences` at the ledger’s top level. Individual readers keep their sets under `task_outputs.supported_consequences`. Record the adjudicator’s resolution without rewriting the two original submissions. The command creates no judgments. Then:

```text
python review_tools.py export-adjudicated REVIEWS.json reviews/reader_2/REVIEWS.json --ledger reviews/ADJUDICATION_v1.json --observer-dir prospective/observer_inputs --out reviews/ADJUDICATED_v1.json --allow-assisted
```

The current root reader file declares prior assistant-draft exposure, so any reference based on it belongs to `assisted_development`. The explicit option retains that classification; it does not waive evidence or completion checks. The default export requires independently submitted, unexposed first-pass judgments. Later assistance must be recorded and cannot retroactively erase exposure or alter the preserved first-pass judgment. The exporter refuses pending or incomplete adjudications.

`evidence_review` in the final ledger concerns an **actual model candidate's evidence chain**, keyed by that candidate ID. It is separate from `evidence_verified` in a human reference. Keep it empty until such a candidate exists and its chain has actually been reviewed.

## Verify context, selection and frozen inputs

Have a map reader who has not screened the dialogue inspect the original map images, inventory every relevant object and independently check cross-map correspondence. Record that reader's identity, prior exposure, image hashes, corrections and evidence outside the observer files. If that reader has screened the dialogue, describe the inventory as assisted and obtain an unexposed check for an independent condition. For Werewolf, establish the exact rule variant, phase and source of any public rule fact. Text without recoverable pointing or speaker information may remain insufficient.

Use `docs/CONTEXT_REVIEW_TEMPLATE.json` as an optional record for this work. It is a provenance form, not an automatic certification. Only after actual verification should the relevant context adapter be marked `verified`.

When a context or prefix changes—including changing an adapter from `draft` to `verified`—create a versioned set of inputs and review records: keep `observer_inputs/CASE.json`, the wrapper `observer_cases/CASE.json` and the curator's `observer_input` identical; retain the old version. Recheck semantic judgments against the new input. Create blank new review slots with `migrate ... --blank` against the new observer directory, or deliberately update the input hash only after rereview and document the earlier hash in metadata. Never silently relabel an old review as referring to new evidence. Human review binding uses exact file bytes, so reformatting observer JSON also changes its raw hash; preserve the frozen file formatting. Rebuild the editor against the frozen directory with `python review_ui.py --root PATH_TO_VERSION --output NEW_REVIEW.html`.

Record actual accepted selections in `pilot_selection.csv` and the corresponding curator/wrapper roles. `include_in_pilot` is one reader's recommendation, not an automatic final selection. Set an accepted evaluation case's `study_role` to `pilot` only after the declared protocol is satisfied. Teaching cases and exposed exploratory material retain their documented role. Treat shared maps and possibly shared game sessions as dependence to assess; different filenames do not prove independent observations.

```text
python prospective/validate_candidates.py
python prospective/validate_candidates.py --baseline
python prospective/build_candidates.py --output-dir NEW_RECONSTRUCTION_FOLDER
```

Normal candidate validation permits review progress; `--baseline` intentionally checks the supplied untouched selection/context state. Reconstruction requires a new/empty destination and does not reset this folder's reviews. It reconstructs the original candidate preparation, including its archived draft context, not a new human selection.

## Run the method

The implemented harness is the staged strict-evidence condition: F1/F2 discovery, F3 candidate readings, separate participant F4 attribution and support checking, then F5 retention, F6 bounded task computation and F7 comparison. One discovered candidate with one hypothesis uses six model requests. Logical stage count is not model-call count.

After contexts and the input condition are verified, make a new run directory, copy `RUN_CONFIG.example.json` into it as `run_configuration.json`, and fill the actual model/version and settings. For UI-only execution, record unavailable settings as unavailable. Then:

```text
python pilot.py prospective/observer_cases/CASE_ID.json runs/CASE_ID_v1 --model-id EXACT_MODEL_VERSION --origin external_model
```

The command writes the next request. Submit only its system/user messages to the declared model in an isolated request, save the untouched reply under the requested `.response.txt` filename and repeat the command. No API connection is built in. Preserve raw failures and provider metadata; duplicate-key or malformed JSON becomes `PROCESSING_FAILURE`, which is separate from `UNRESOLVED`. Use a new run directory for changed code, prompt, configuration or evidence.

Only the four observer fields and prior model-stage outputs enter this pipeline. Never supply `REVIEWS.json`, wording, selection specifications, curator drafts, suffixes or reference labels as model input. F2 must discover expressions from the full unmarked prefix, not receive the human focus.

```text
python report_results.py runs --references reviews/ADJUDICATED_v1.json --out results/pilot_v1.json
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
