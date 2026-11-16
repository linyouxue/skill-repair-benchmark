# Opus Gold15 JPG incremental refresh

## Scope

- Only `jpg-ocr-stat` was replaced. The other 14 task bundles and selections are inherited unchanged from `evaluation/results/SkillOpt-Opus47-Gold15-JPGRefresh-20261025/runs/opus47-15-skillopt-opus47-tatu-20261008`; their current aggregate entries are in this directory's `submission.json` and `run_status.json`.
- The published JPG package came from `linyouxue/skill-repair-benchmark` snapshot `64e7ca807b19b8e3c19e96853a50f175e6dbdb19`.
- No public three-group generalization images were used for diagnosis, repair, selection, or scoring.

## SkillOpt repair

- Model/provider: `claude-opus-4-7` through Tatu.
- Configuration: patch mode, `L=4`, `R=2`, same-task keep/revert gates.
- The published Opus baseline workbook scores `40/44 = 0.9090909091` under the same new field verifier (21 dates, 19 amounts, 18 joint receipts).
- Round 1 diagnosis consumed all 37 published windows. Every request delivered 22 real image content blocks and retained the provider-shaped request and complete response.
- Round 1 gate: `43/44 = 0.9772727273`, decision `keep`.
- Round 2 gate: `39/44 = 0.8863636364`, decision `revert`.
- Frozen selection: the round 1 candidate, bundle SHA-256 `308ba3999891b130089e78fb4ce2cf97f425798d22d929a4545e000645a17a61`.

## Frozen final execution

- Run ID: `jpg-ocr-stat-skillopt-20261025T080609Z`.
- Effective parent-iteration cap: 65; natural completion after 31 iterations.
- Result: `44/44 = 1.0`; 22/22 dates, 22/22 amounts, and 22/22 joint receipts correct.
- Health: execution, protocol evidence, iteration accounting, Skill exposure, and trajectory completeness all passed.
- Real workbook: `evaluation/results/SkillOpt-Opus47-Gold15-JPGRefresh-20261025/runs/opus47-gold15-jpg-final-20261025/jobs/skillopt/jpg-ocr-stat-skillopt-20261025T080609Z/artifacts/stat_ocr.xlsx`.
- Workbook SHA-256: `19c7f2efe59e073298a6f8d86a8fbfafd4d759a842f51c761539b0d15cb69692`.

## Preserved invalid attempts

- `opus47-gold15-jpg-refresh-20261025`: diagnosis succeeded, but two gates were rejected before Agent execution because the package's offline `tests/` directory was interpreted as a second runtime verifier.
- `opus47-gold15-jpg-refresh-v2-20261025`: the Agent executed, but the old result seam rejected the configured 65-iteration cap because it still hard-coded 60; one superseded retry was interrupted after that cause was identified.
- Both runs remain raw evidence and are excluded from scoring.

## Data split disclosure

There is no independent validation split or held-out final-test split. Candidate keep/revert uses the original 22-receipt task. The reported result is a separate execution of the frozen selected Skill on those same 22 receipts, not a held-out generalization score.

## Entry points

- `submission.json`: evaluator-facing 15-task submission.
- `run_status.json` and `summary.csv`: selected health and scores.
- `evidence_index.json`: task-to-run, repair-loop, rollout, terminal-log, and invalid-run provenance.
- `experiment_manifest.json`: exact composite selection and raw-run roles.
