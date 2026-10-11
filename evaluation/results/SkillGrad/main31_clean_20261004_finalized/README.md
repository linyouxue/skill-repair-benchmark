# MAIN31 clean experiment: first two finalized tasks

This directory is a partial, outcome-only publication of the MAIN31 clean experiment. It is separate from the earlier representative/partial archive in `evaluation/results/SkillGrad/tasks/`. Neither task passed: both reached `S5_FAIL`. The remaining MAIN tasks are not represented here.

| Task | Execution origin | Final status | Valid formal rounds | Notes |
| --- | --- | --- | --- | --- |
| `dialogue-parser` | Historical clean canary, carried forward after compatibility audit | `S5_FAIL` | S0-S5 | One infrastructure-invalid S1 attempt preceded the valid S1 retry. It was **not** executed with the final frozen v1 code SHA. |
| `lab-unit-harmonization` | Frozen `final_main31_v1` execution | `S5_FAIL` | S0-S5 | S3 formal was retained; its repair was completed in isolated recovery attempt `s3_repair_restart_001` and promoted to S4 without rerunning S3 formal. |

The per-task JSON files contain the canonical final verdict, formal-round reward and rollout identity, and SHA-256 references to the authoritative result and ledger at export time. The summaries are derived records, not replacements for canonical evidence. The `infrastructure_invalid` attempt is listed for accounting but is not a method failure or an extra repair round.

Raw trajectories, task data, verifier/Gold materials, hidden tests, model transcripts, credentials, and server-specific paths are intentionally not published in this directory. The final frozen v1 manifest was checked read-only: 207/207 frozen files matched.
