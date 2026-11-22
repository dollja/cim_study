# Method

The procedure takes a dialogue prefix and decides whether two participants' readings of a point
in it would lead to different task outcomes. It is implemented in `src/pilot.py`.

## Input

For each case the model receives exactly four fields:

| Field | Content |
|---|---|
| `overall_task` | One sentence describing the task |
| `participants` | Participant identifiers and known roles (for example giver, follower) |
| `context_sources` | Text each participant can see: the landmark list of their own map, or the public game instructions, with a record of who has access |
| `dialogue_prefix` | The utterances up to the cutoff, each with an identifier, speaker and text |

Nothing else is sent: no later dialogue, no reviewer label, no marked point of interest.
`check_view` rejects an input that contains any other field.

## Stages

1. **Discovery (model, stages F1–F2).** From the unmarked prefix the model proposes up to three
   candidate points where an interpretation matters for the task. For each it names two
   participants and gives one to three hypotheses about the sub-task at stake. Sub-tasks are
   `anchor`, `route`, `checkpoint` (maps), `holder`, `target` (game), `review_date` and `outside`.
   Every proposal must quote the dialogue or context exactly.
2. **Readings (model, F3).** For each hypothesis the model lists the plausible meanings as
   structured arguments, before saying who holds which.
3. **Attribution (model, F4, once per participant).** The model judges each reading as supported,
   contradicted or undetermined for that participant. A reading is supported only through a path
   that starts in the participant's own words: saying, instructing or explicitly endorsing. Access
   to information, or a bare acknowledgement, does not count.
4. **Check (model, separate call).** A second call rechecks every reading and every support path
   against the quoted evidence.
5. **Retain (code, F5).** A reading is kept for a participant only if attribution and check both
   mark it supported and every quotation is an exact substring of text that participant could
   see. Corrections and withdrawals by the same speaker remove the earlier reading.
6. **Task consequence (code, F6).** Each kept reading is mapped by fixed rules to a task outcome,
   for example "route passes below landmark class K" or "role R is held by player P". If the rules
   cannot compute an outcome, or an argument has the wrong type, the outcome is unknown.
7. **Compare (code, F7).** The two participants' outcome sets are compared.

| Outcome sets | Label |
|---|---|
| The same single outcome for both | aligned |
| Both known, with no outcome in common | potential mismatch |
| Anything missing, unknown, overlapping or blocked | unresolved |

A candidate takes the label shared by all its hypotheses, otherwise unresolved. A case is a
potential mismatch if any candidate is; otherwise unresolved if any candidate is unresolved or
discovery reported more than three candidates; otherwise aligned.

## Limits of the rule-based stages

- Route outcomes are compared only for seven relations: above, below, left of, right of, around,
  toward, away from.
- Map outcomes need a landmark that appears in the participant's verified landmark list.
- Game outcomes need the role, phase and premise to be stated as single values.

## Running

`src/run_pilot_sync.py` sends one streamed request per stage, saves each reply unchanged with its
hash, and logs every attempt with its cost. A call that returns nothing, or is cut off at the
output limit before any answer text, is sent again with the same request. The runner forces IPv4
because replies were lost on the IPv6 route of the network used for the study.

Each case needs between 6 and 46 model calls, depending on how many candidates and hypotheses the
model proposes.
