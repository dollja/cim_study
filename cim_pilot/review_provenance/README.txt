R1 PREPARATION HISTORY

These files preserve the source and editing history of the current r1 review.
They are research records. They are never part of model-visible observer inputs.

The active review files omit the repeated preparation paragraphs formerly present
inside every case. R1_PREPARATION_HISTORY.json preserves those paragraphs with
source hashes and the exact changed JSON paths. The source_snapshots directory
contains the unchanged review versions used for this update and the previous
package-root review. An older snapshot is not a second reader submission.

The active records retain the required, previously declared prior-exposure flag,
the existing wording-field history, the actual completion flags and the existing
reference condition. Moving verbose history into this directory does not change
the conditions under which the reviews were prepared.

On 2026-11-13 the user explicitly requested MT10 blocking_uncertainty=false.
That change was applied in both versions. The saved ALIGNED choice remains, as
do the two null START arguments. The resulting decision inconsistency is recorded
in CURRENT_READINESS.json. No map verification or new human confirmation was
created by the edit.

REVIEWS.json is the active r1 v3 copy. Keep a dated snapshot before further review,
before revealing model outputs, and before discussing another reader's decisions.
Record new exposure at the time it happens; do not rewrite the earlier history.

READABLE KEY CORRECTION

The readable-key revision changes field names only. JSON_KEY_RENAME_RECORD.json
records source and output hashes and exact reverse-conversion checks. Clean review
snapshots from before this key conversion are retained under
key_format_source_snapshots/. These snapshots are the same human submissions,
not new reviews. Legacy and readable keys normalize to the same review content
for existing comparison and adjudication hashes.
