# Baseline audit

- Coverage: 15 expected, 15 present, 0 missing, 0 duplicate.
- Outcome filter: all 15 selected trajectories are baseline failures.
- Deterministic artifact gate: 15 healthy, 0 unhealthy. Every rollout has parseable ACP and LLM trajectories plus scoring metadata.
- The source archive stored LLM JSONL files as gzip. The isolated imported copies were losslessly decompressed while retaining the `.gz` originals so the validator could inspect them.
- Task-skill loading: 15 of 15 recovered automatically from startup evidence.
- Verdict: baseline inputs are usable. Repaired runs must pass the same artifact and comparability gates before export.
