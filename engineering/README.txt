CONSTRUCTED ENGINEERING INPUT

observer_cases/ENGINEERING_FIXTURE_01.json is a new wrapper containing only the observer view returned by tests.test_pilot.fixture()[0]. The separate candidate, hypothesis, readings, attributions and support checks returned by that fixture were not copied.

The model-visible view contains the task, participant IDs, two explicit constructed dialogue turns and two stipulated map inventories. It contains no expected label, human focus, supplied hypothesis or research annotation. input_validation.json records the schema check, recursive annotation-key scan, source identity and hashes. This check did not call a model.

study_role=engineering_fixture keeps this input distinct from empirical pilot cases. Its inventory review_status=verified denotes internally stipulated fixture facts, not independent human verification of a real map. Do not change the fixture's role to pilot or count it among the 20 candidates.

CODEX_RUN_PROMPT.txt permits one genuine-model engineering smoke on this fixture only when no real case is execution-eligible. Preserve actual requests, raw model responses and provider records in a separate engineering run directory. Do not use expected test outputs or replay records as model responses. No prediction or measured-result placeholder is supplied here.
