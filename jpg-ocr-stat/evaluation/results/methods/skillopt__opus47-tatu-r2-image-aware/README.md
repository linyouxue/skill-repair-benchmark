# SkillOpt / Opus-4.7 Tatu / group 2

- Skill: `jpg-ocr-stat/result/skillopt__opus47-tatu-r2-image-aware/skills/` in the same commit; frozen bundle SHA-256 `308ba3999891b130089e78fb4ce2cf97f425798d22d929a4545e000645a17a61`.
- Data: `group_02` from repository `main` commit `242773b29`; 20 receipts and 40 date/amount fields per run.
- Configuration: `tatu/claude-opus-4-7`, OpenHands ACP Agent, BenchmarkExecutor/BenchFlow v0.6.7, at most 65 parent iterations per run.
- Independence: all three executions started from a freshly prepared group-2 task. The same frozen Skill was used without modification; group-2 results were not used to repair or select it.
- Evidence: each `group_02/run_0N/` includes the real `stat_ocr.xlsx`, full ACP trajectory, losslessly gzipped full LLM trajectory, original and offline verifier records, configuration, timing, token/cost records and a healthy trajectory audit.
- Integrity: `group_02/metadata/` contains the credential-scan report and SHA-256 manifest.

| Group | Run 1 | Run 2 | Run 3 | Mean |
|---|---:|---:|---:|---:|
| `group_02` | 29/40 (72.50%) | 38/40 (95.00%) | 36/40 (90.00%) | 103/120 (85.83%) |

| Run | Run ID | Date | Amount | Iterations | Stop |
|---|---|---:|---:|---:|---|
| 1 | `jpg-ocr-stat-skillopt-20261102T055052Z` | 19/20 | 10/20 | 49/65 | `end_turn` |
| 2 | `jpg-ocr-stat-skillopt-20261102T055136Z` | 20/20 | 18/20 | 22/65 | `end_turn` |
| 3 | `jpg-ocr-stat-skillopt-20261102T055201Z` | 20/20 | 16/20 | 15/65 | `end_turn` |

All runs completed normally. `task_passed=false` in their metadata means only that this verifier reserves pass for 40/40; it is not an infrastructure or trajectory-health failure.
