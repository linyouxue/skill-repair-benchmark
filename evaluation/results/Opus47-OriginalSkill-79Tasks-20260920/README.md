# Claude Opus 4.7 Original-Skill SkillsBench

79 tasks: **50 PASS, 29 FAIL**. Successful reruns and verifier recoveries count as PASS. See [task names](PASS_FAIL_REPORT.md) and [selected runs](final_task_results.json).

`runs/opus47-original-skill/` retains every available attempt with agent/provider trajectories, verifier outputs and metadata. Historical attempts without a completed verifier remain recorded as such; all 79 selected outcomes have trajectories, verifier stdout and rewards. CTRF reports are included wherever produced by the original verifier; seven task verifiers did not emit CTRF. `FILE_MANIFEST.json` enumerates every retained run file.

LLM trajectories and files larger than 40 MB are losslessly gzip-compressed for GitHub. Run `python restore_trajectories.py` to restore their original filenames; files still exceeding GitHub limits are split into `.part001`, `.part002`, etc. and automatically reassembled by that script; no events are omitted. Local batch files remain uncompressed.

Druid uses the original model trajectory with 14 recorded edits replayed against the same baseline, rebuilt, and verified 4/4. ADA uses original exported artifacts and verifier-only recovery (6/6). Effective results are PASS; `verification_recovery/original/` retains the original results, while `verification_recovery/evidence/` records recovery provenance and verifier output. These are not additional model rollouts.

`summary.json` and `batch_state.json` preserve the original local-only accounting and scheduler state. `final_task_results.json` is the final 79-task P/F index including the server task. Unknown model costs remain unknown.
