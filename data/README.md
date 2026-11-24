# Data

## Input sets (`inputs/`)

An input set is a folder of cases exactly as they are given to the model, with a `manifest.json`
that records a SHA-256 hash for every file. `src/verify_frozen_inputs.py` checks a set against its
manifest, and the runner refuses to start if the check fails.

| File or folder | Content |
|---|---|
| `manifest.json` | File hashes, the hash of each case, and how the context was verified |
| `pilot_selection.csv` | One row per case: source dialogue, map pair or game, cutoff utterance |
| `prospective/observer_inputs/` | The four-field input for each case (what the model sees) |
| `prospective/observer_cases/` | The same input with its case identifier (read by the runner) |
| `prospective/curator_cases/` | The input plus material never sent to the model: annotations and later dialogue |

`CIM_INPUTS_20261113_V1` (Set B) also holds the source transcripts, map images, row-to-source
crosswalks, and the screening and selection records for its 20 cases. Its manifest was reduced on
2026-11-22 when review pages and case-building scripts were moved out of the repository; the
manifest records this and the hash of the original. The observer inputs are unchanged.

`CIM_INPUTS_20261121_SETA_V1` (Set A) holds the 20 Set A cases and
`CIM_INPUTS_20261121_SETA_CONTROLS_V1` the eight paired controls. Both are built by
`src/build_set_a.py`; the selector's case file, screening log and selection summary are under
`source/` in each set.

Context for Set A follows Set B. Map Task cases reuse its verified landmark lists unchanged; the
lists for map pair m2, which Set B does not use, are in `context/`. Werewolf cases use the Set B
task description and standard role list; the instructions text is what a recorded game-audio
speaker says in the prefix, and where there is none the text states only that and the role list.
Participants are the players the selector listed.

## Context (`context/`)

`m2_landmark_lists.json` holds the landmark lists for the two m2 maps, drafted from the map images
and the published landmark table and confirmed by the study author on 2026-11-23.

## Reviews (`reviews/`)

| File | Content |
|---|---|
| `forms/reviewer_interface.html` | Reviewer form for Set A (self-contained; opens in a browser) |
| `forms/reviewer_interface_setB.html` | The same form for Set B |
| `forms/adjudication_setA.html` | Adjudication form for the 12 Set A cases on which the two reviews differ: the Set A form with the two earlier answers shown as Review X and Review Y. Built by `src/build_adjudication_form.py` |
| `labels/setA_reviewer_1.csv`, `labels/setA_reviewer_2.csv` | Two independent reviews of Set A, as exported by the form |
| `labels/setA_adjudication_key.csv` | Which review is shown as X and which as Y in the adjudication form (not for the adjudicator) |
| `labels/setB_initial_review.csv` | The initial single review of Set B, made before the form existed and with an AI assistant's drafts in view |

The form shows the task, the two people to compare, a task question and the dialogue up to the
stopping point, and offers three answers: different outcome, same outcome, not enough
information. The exported `formal_label` is `potential_consequential_mismatch`,
`aligned_or_consequence_equivalent` or `unresolved`.

## Provenance (`provenance/`)

Records for Set B that its manifest refers to: the context verification, the accepted selection
and the transition of the inputs to their verified form.

## Sources

| Source | Used for | Reference |
|---|---|---|
| HCRC Map Task corpus v2.1 | Map Task dialogues and maps | https://groups.inf.ed.ac.uk/maptask/ |
| Grounded Misunderstandings in MapTask | Landmark tables and reference annotations | https://github.com/chnln/grounded-misunderstandings-in-maptask |
| Werewolf Among Us | One Night Ultimate Werewolf transcripts | https://huggingface.co/datasets/bolinlai/Werewolf-Among-Us |

Source revisions and file hashes for Set B are in
`inputs/CIM_INPUTS_20261113_V1/prospective/provenance/` and `.../source_maps/provenance.json`.
The corpora remain subject to their original licences. Full copies are not redistributed here.
