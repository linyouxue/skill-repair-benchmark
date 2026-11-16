# SkillOpt Opus-4.7 Gold15 and JPG refresh

This directory contains the current Opus-4.7 SkillOpt result set. It is fully
separated from the GPT-5.2 experiment in
`../SkillOpt-GPT52-31-EvidenceFix-20261018/`.

## Start here

1. `submission/summary.md` — headline result counts.
2. `submission/summary.csv` — one selected result for every Gold15 task.
3. `submission/run_status.json` — health, scores, selected stages, models, and source runs.
4. `submission/evidence_index.json` — links from each task to diagnosis, candidates, gates, trajectories, verifier output, and logs.
5. `submission/JPG_REFRESH_REPORT.md` — the multimodal JPG diagnosis and field-verifier result.
6. `submission/submission.json` — evaluator-facing standardized submission.

## Result

- 15/15 selected task results are healthy and comparable.
- 7 tasks passed and 8 tasks failed.
- Passing tasks: `azure-bgp-oscillation-route-leak`, `data-to-d3`,
  `jpg-ocr-stat`, `manufacturing-equipment-maintenance`, `paper-anonymizer`,
  `pddl-airport-planning`, and `seismic-phase-picking`.
- The refreshed `jpg-ocr-stat` final execution scored `44/44 = 1.0`. Its
  published Opus baseline scored `40/44`, round 1 scored `43/44` and was kept,
  and round 2 scored `39/44` and was reverted. The frozen round-1 Skill then
  scored `44/44` in the separate final execution.
- The other 14 task selections are unchanged from the 2026-10-08 Gold15 run.
- Selection used same-task keep/revert gates. There was no independent
  validation set and no held-out final-test set.

## Raw runs

- `runs/opus47-15-skillopt-opus47-tatu-20261008/`: original complete Gold15 run; supplies the 14 unchanged selections.
- `runs/opus47-gold15-jpg-refresh-20261025/`: complete 37-window multimodal diagnosis and preserved infrastructure-invalid gates.
- `runs/opus47-gold15-jpg-refresh-v2-20261025/`: preserved hard-coded iteration-limit failure and interrupted retry.
- `runs/opus47-gold15-jpg-refresh-v3-20261025/`: healthy two-round JPG optimization.
- `runs/opus47-gold15-jpg-final-20261025/`: separate frozen-Skill final execution and workbook/verifier evidence.

The uploaded raw runs retain optimizer inputs and complete responses, diagnosis
samples, candidate Skill packages, gate attempts, executor trajectories,
verifier evidence, terminal commands, and keep/revert decisions. Publicly
available baseline job copies and source-task snapshots are referenced in
`PUBLIC_SOURCES.md` instead of duplicated.

One 114,444,900-byte trajectory exceeds GitHub's 100 MB per-file limit. Its
exact uncompressed bytes are stored as three ordered files in the adjacent
`llm_trajectory.jsonl.parts/` directory. See `SPLIT_FILE_MANIFEST.json` for
checksums; concatenating the parts reproduces the original SHA-256 exactly.

`metadata/SECURITY_SCAN.json` records the credential scan, and
`metadata/FILE_MANIFEST.sha256` provides package checksums.
