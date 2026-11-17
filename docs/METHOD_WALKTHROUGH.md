# Current method: from dialogue evidence to a consequence comparison

Reference: the 20-slide **Integrated Early Warning** deck dated 2026-11-06, including speaker notes. Numbers below refer to that deck, not earlier 40-slide versions. The complete Chapter 3–4 PDF was not among the three attachments used for this update.

## One-minute explanation

CIM asks whether two participants' expressed interpretations of the same local task question imply compatible task consequences. First identify the question and language; construct plausible readings; determine which readings each participant's own evidence supports; compute consequences; then compare the resulting sets. A difference in map inventory, a different word, a false claim or a brief acknowledgment is not by itself an interpretation mismatch. The framework can remain unresolved when the observation does not justify a definite conclusion.

## Logical stages and implementation

| Stage | Human review question | Current implementation | Current slides |
|---|---|---|---|
| F1 | What local task question is being settled? | Structured discovery request; up to three candidates/hypotheses, full prefix | 6–7 |
| F2 | Which speakers and exact expression are compared? | Participant pair, source IDs, exact spans and event scope from discovery | 6–7 |
| F3 | What readings are plausible before attribution? | Structured candidate-reading request; retain coverage uncertainty | 6, 8 |
| F4 | Which reading does each participant's speech support? | Separate participant attribution plus separate support-check requests | 4, 6, 8 |
| F5 | Which evidence chains survive the policy? | Code checks source, access, ownership, scope and declared semantic support; corrections/withdrawals are scoped | 4, 8 |
| F6 | What task outcome follows from each supported reading? | Bounded deterministic adapters; missing required arguments stay unknown | 8–9 |
| F7 | Same singleton, disjoint known sets, or unresolved? | Shared consequence-set comparison with blocking-uncertainty guard | 9 |

The slides group these as Find, Construct, Compute and Compare. That grouping does not mean there are four model requests or seven calls. For one candidate/hypothesis the current staged harness uses six requests and then local computation. Its prompts operationalize the method; they are not a claim to reproduce final verbatim research prompts.

## Tier S: availability, possibility and expressed support

Slide 4 and its notes require an observable participant record. Map/rule availability establishes what a participant could access. F3 records possibilities; F4–F5 determine supported readings. These cannot be collapsed into one step. Use earlier expressed evidence when it grounds a later acknowledgment. A bare acknowledgment with no such grounding does not establish adoption. Questions, attributed claims and conditional reports need speech-act and event/phase review.

The software can test exact quotations, permitted sources and declared argument structure. It cannot certify that the semantic reading or support check is correct. A model's separate support check remains a model output to evaluate.

## The comparison on slide 9

Let `G_A` and `G_B` be the known consequences of each participant's supported readings for the same frozen task function. `ALIGNED` requires equal singleton sets. `POTENTIAL_MISMATCH` requires nonempty disjoint sets. Other cases are `UNRESOLVED`. A blocking unknown takes precedence. An unresolved alternative that adds no new possible consequence need not block; an unknown or additional consequence does.

| Supplied consequences | Blocker | Result |
|---|---|---|
| A = `{above(pine)}`; B = `{above(pine)}` | false | `ALIGNED` |
| A = `{above(pine)}`; B = `{below(pine)}` | false | `POTENTIAL_MISMATCH` |
| A = `{above(pine), below(pine)}`; B = `{above(pine)}` | false | `UNRESOLVED` |
| A = `{above(pine)}`; B = empty | false | `UNRESOLVED` |
| A = `{above(pine)}`; B = `{above(pine)}` | true | `UNRESOLVED` |

These are constructed examples of the rule, not assigned labels for corpus cases. Consequence equality is defined by the declared task representation; do not compare differently scoped prose strings or choose the representation after seeing a desired label.

## What the examples illustrate

- **Slides 3 and 10: Q3.** Two available calendar interpretations plus acknowledgment remain unresolved; explicitly expressed choices permit comparison. This is a constructed diagnostic.
- **Slide 11: MapTask.** Supported, different anchor choices can imply different route consequences. The retained software fixture gives both maps both anchors to test common inventory handling; it is adapted and is not identical to the slide stimulus.
- **Slide 12: Werewolf.** Compare a reported exchange under a declared conditional premise, with participant, role, event, phase and operation order bound. Hidden actual roles do not enter the observer record.
- **Slide 13: optional later action.** Later action and requirement checks are separate from primary early-warning labels. Keep the later suffix and `Met`/`Not-Met`/`Cannot-Determine` results separate.

## What the planned comparisons would establish

Slide 15 proposes three construction arms with a shared F6/F7 function: an end-to-end structured construction, staged prompt aggregation and explicit F5 evidence retention. Only the current staged strict-evidence harness is implemented here. A fair comparison must hold model, inputs, task functions, consequence representation, budgets and evaluation references constant where the protocol requires it.

Component tests isolate support filtering, alternative handling, attribution scope and task computation. They show that stipulated inputs are handled as intended; they do not show model accuracy. Joint-versus-separate construction is a diagnostic design, not a completed comparative result. Warning lead time needs successive eligible prefixes and independently identified repair/discovery events. A correct label at one cutoff, especially a post-correction cutoff, cannot establish early warning.

## Preparation versus findings

Slides 16–18 report the state saved before this update: 20 candidates, no finalized selection or adjudicated reference, 26 software tests in an archived record, one constructed mismatch replay and six supplied-record replays. The latter yielded four alignments and two unresolved statuses, with map-dependent and post-repair qualifications. Fresh software checks belong in a new dated record. Neither set of software checks supplies an empirical model-performance denominator.

The current materials make selection, context verification, review, adjudication and later model execution traceable. They do not recover an absent earlier selection manifest, certify independent sampling or invent Chapter 5 results.
