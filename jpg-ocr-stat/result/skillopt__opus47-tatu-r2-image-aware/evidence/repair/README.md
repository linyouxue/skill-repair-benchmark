# Repair evidence

The complete SkillOpt JPG repair archive is public at commit `fdedc4277a67d460db5ef4cf4a82e47b91f3058a`:

`evaluation/results/SkillOpt-Opus47-Gold15-JPGRefresh-20261025/runs/opus47-gold15-jpg-refresh-v3-20261025/methods/skillopt/jpg-ocr-stat/`

That path preserves all 37 image-aware diagnosis requests and responses, both candidate Skill packages, rewrite proposals, gate executions and trajectories, verifier outputs, keep/revert decisions, and rejected-buffer state. The adjacent job directories at the same commit preserve the round-1 and round-2 executor runs.

This directory mirrors the most important navigation records:

- `repair_loop.json`: cross-round candidate, score and selection history.
- `round_1/`: the accepted 43/44 proposal and gate.
- `round_2/`: the rejected 39/44 proposal and gate.
- `round_1/diagnosis_samples/sample_1.json.gz`: a complete, losslessly compressed request/response showing actual image content blocks.
- `jpg_window_coverage.json`: proof that all 37 published diagnosis windows were consumed in round 1.
- `diff.patch`, `diagnosis_report.*`, and `method_result.json`: final repair summary.

No independent validation set was configured. Candidate selection used same-task keep/revert gates; the later group-2 evaluation was not used for selection.

