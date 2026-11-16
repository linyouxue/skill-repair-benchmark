# SkillRevise / Claude Opus 4.7 field22 r1

Final bundle frozen before any generalization access.
Source materials: 64e7ca807b19b8e3c19e96853a50f175e6dbdb19/jpg-ocr-stat/diagnosis; source Opus run retained as historical evidence.
Diagnosis/revision model: claude-opus-4-7; final Agent: tatu-anthropic/claude-opus-4-7; original SkillRevise top3/3 revisions, BM25.
Final rollout: jpg-ocr-stat-final65-c856d1046685; cap check=True; configuration and actual records: evidence/repair/final_65_iteration_override.json and evidence/final_run/result.json.
Actual Excel: evidence/final_run/artifacts/stat_ocr.xlsx. Reward=0.9772727272727273; task_passed=False.
See evidence/repair for real prompts, image blocks, revisions and frozen-file hashes.
Human involvement: adapter/runtime integration only; no manual Skill edits in this workflow.
Generalization has not been run. Missing artifacts/infra errors remain reported in final_checks.json.

## Three independent original22 final executions
Same frozen Skill, same Opus route, each capped at 65 parent iterations. All results retained.

| Run | Field accuracy | Run ID |
|---|---:|---|
| 1 | 0.97727273 | jpg-ocr-stat-final65-c856d1046685 |
| 2 | 0.86363636 | jpg-ocr-stat-final65-run2-a874eefea7c9 |
| 3 | 0.95454545 | jpg-ocr-stat-final65-run3-f5805cc0c276 |

Arithmetic mean: 0.93181818.
Run 1: evidence/final_run/; runs 2/3: evidence/final_runs/run_02/ and run_03/. Each contains native Excel, trajectory, scoring and execution metadata. Generalization not run.

## Upload status and scope

Original22 repair and three final evaluations are complete. Group2 generalization has NOT been run. No generalization result is claimed.
Credential scan/redaction and original/exported file hashes: evidence/export_manifest.json. Only credential strings may be redacted; native Excel files and reported scores are unchanged.
