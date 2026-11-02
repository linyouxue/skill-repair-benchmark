# SkillOpt / Opus-4.7 Tatu / image-aware two-round repair

- Final Skill version: frozen five-Skill bundle in `skills/`; SHA-256 `308ba3999891b130089e78fb4ce2cf97f425798d22d929a4545e000645a17a61`.
- Method and code: SkillOpt, two repair rounds. The complete raw repair record is pinned to the `skillopt` branch at commit `fdedc4277a67d460db5ef4cf4a82e47b91f3058a`, under `evaluation/results/SkillOpt-Opus47-Gold15-JPGRefresh-20261025/`. Essential decisions, proposals and one losslessly compressed multimodal request are mirrored in `evidence/repair/`.
- Models and harness: repair and final execution both used `tatu/claude-opus-4-7`; final runs used the OpenHands ACP agent through BenchmarkExecutor/BenchFlow v0.6.7 (`aadad44acf27f193df98f438443116d514f51fb8`) with a 65-parent-iteration limit.
- Repair material: the original 22-receipt task, Opus-4.7 baseline failure evidence, and the published 37-window diagnosis package. Round 1 scored 43/44 and was kept; round 2 scored 39/44 and was reverted. There was no separate validation set: the two gates used the same original task. Group 2 was not used for diagnosis, repair, gating or frozen-version selection.
- Image input: the repair adapter sent real image content blocks. `evidence/repair/round_1/diagnosis_samples/sample_1.json.gz` preserves a complete request/response example; all 37 requests are available at the pinned public repair path above.
- Human involvement: orchestration, infrastructure recovery, evidence packaging and verification only. The final Skill was not manually edited after SkillOpt selection and was not changed after group-2 scores became visible.
- Trajectories: each final run retains the full ACP trajectory and a losslessly gzipped full LLM trajectory. `trajectory_audit.json` reports each counted run as healthy.
- Infrastructure disclosure: one same-second Docker project-name collision occurred before run 3 and is preserved in `evidence/invalid_attempts/`; it never entered the Agent and is not counted as one of the three final runs.

| Original 22 receipts | Run 1 | Run 2 | Run 3 | Mean |
|---|---:|---:|---:|---:|
| Field accuracy (44 fields/run) | 44/44 (100.00%) | 39/44 (88.64%) | 42/44 (95.45%) | 125/132 (94.70%) |

| Run | Run ID | Date | Amount | Iterations | Stop | Evidence |
|---|---|---:|---:|---:|---|---|
| 1 | `jpg-ocr-stat-skillopt-20261025T080609Z` | 22/22 | 22/22 | 31/65 | `end_turn` | `evidence/final_runs/run_01/` |
| 2 | `jpg-ocr-stat-skillopt-20261102T051639Z` | 19/22 | 20/22 | 38/65 | `end_turn` | `evidence/final_runs/run_02/` |
| 3 | `jpg-ocr-stat-skillopt-20261102T052140Z` | 20/22 | 22/22 | 26/65 | `end_turn` | `evidence/final_runs/run_03/` |

The three independent scores vary because the frozen Skill fixes instructions, not Opus/OCR sampling. All three `executor_request.json` and `result.json` files record the same configured and observed Skill bundle hash. Errors and lower-than-baseline runs are retained rather than cherry-picked.
