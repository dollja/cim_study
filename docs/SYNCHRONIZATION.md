# Synchronization record — 2026-11-09

**Historical method-synchronization record.** Current review progress and the readable-key correction are recorded in the root `README.md`, `CURRENT_READINESS.json` and `validation/human_keys_20261113/`. The original draft-state descriptions below describe the 2026-11-09 package, not the current r1 submissions.

## Supplied inputs

| Input | SHA-256 |
|---|---|
| `pcc_pilot-main.zip` | `800f6aba13b2550354d9471e5379b10e8d0eefcb05cde815573cfdd886ff5de7` |
| `Tier_S_Review_Wording_Package(1).zip` | `fe7e517e5031d2d659bc006c23afdd85a5581c69311bda115046f75cb25ff1cf` |
| `PCC_Early_Warning_Integrated_2026-11-06(1).pptx` | `cf3bfb81c30a730afdcb6e2009d95e949fc6809e4e37db6f1f5eacd1be1b4fce` |

The integrated deck has 20 slides. Both slide XML and speaker-note XML were inspected. The full chapter PDF was not included, so the synchronization claim is limited to these supplied sources. The attachments remain unchanged; this is a new working package.

## Decisions and changes

- Kept the requested stable substantive JSON keys and the three controlled label codes. Added short UI captions, exact `focus_quotes`, separate `prefix_only_rationale` and structured `review_metadata`. Moved legacy process flags into metadata. Added `support` on each proposed reading; migrated suggestions start null.
- Populated the main review from wording alternative A, with alternative B separately available. Preserved recorded reviewer/progress/exposure history and left all missing human labels, inclusion and evidence checks pending. One historical `reviewed` flag remains incomplete under the current content/completeness checks.
- Added the canonical schema, metadata field dictionary, migration, validation, difference report and explicit adjudication export. Exports bind reader submissions by hash and distinguish independent from assisted references. They do not auto-adjudicate.
- Added an offline editor with blank initial state, complete unmarked prefixes, explicit review/wording imports and download-based saving. It does not send network requests or synchronize files automatically. Suggestions are opt-in and exposure is recorded.
- Retained the original F7 comparison. Corrected the blocker for unresolved alternatives: a known alternative already contained in a supported consequence set does not add uncertainty merely because that set contains several outcomes. Unknown or additional consequences still block.
- Made Tier S explicit in saved method identities; closed nested observer structures against hidden annotations; preserved exact raw response byte hashes; distinguished malformed replies from substantive unresolved judgments.
- Bound adjudicated references to the raw input file and the same canonical observer hash used by runs; reporting requires matching evidence and excludes unbound legacy references from current scoring.
- Separated reference conditions in reporting and named source grouping without implying independent participants or sessions. Preserved the distinction between human evidence verification and candidate-specific model evidence review.
- Made candidate regeneration use a new destination; source validation no longer forces reviewed cases to remain at their initial draft state. Archived result files are not overwritten by fresh verification.
- Updated references to the current slides; marked earlier code walkthroughs as adapted/supplied fixtures. Personal attributions and name-bearing selection metadata were replaced with neutral wording, without changing transcript bytes.

## Evidence boundaries

| Location | Content | Primary model input? |
|---|---|---|
| `prospective/observer_inputs/` | The four allowed input fields | Yes, after declared context verification |
| `prospective/observer_cases/` | Case wrapper and the same four-field observer object | Harness consumes only `observer_input` |
| `REVIEWS.json`, `reviews/`, `wording/` | Research judgments, provenance and assistance | No |
| `prospective/curator_cases/` | Selection focus, drafts, annotations and later suffix | No |
| `prospective/selection_specs.json`, `screening_log.json` | Preparation/screening proposals | No |
| `source_examples/`, `reference_drafts/` | Exposed teaching annotations | No |
| `validation/`, replay outputs | Software verification and stipulated traces | No; not empirical model outputs |

Neither hiding a panel nor renaming a field makes a contaminated observer file safe. The editor embeds only the four-field observer inputs; the inference harness applies structural allowlists. Humans still assess the semantic support and provenance of permitted content.

## Implemented versus pending

Implemented: the staged strict-evidence offline harness; bounded task adapters; consequence-set comparison; reproducible request/reply files; review tooling; source validation; descriptive reporting by reference condition.

Pending: actual selections, independent map/rule review, completed human references, actual model execution, all slide-15 comparison arms, matched-budget comparisons, successive-prefix timing and any separate optional action/requirement experiment. No empirical accuracy, precision, recall, F1, lead time or superiority result is claimed.

See `validation/verification_summary.json` for the fresh executed checks and their limits. Old logs under `cim_codex_handoff/` retain their archived scope. Historical checksum lists describe the older input package; the root `PACKAGE_CHECKSUMS.json` describes this returned package.
