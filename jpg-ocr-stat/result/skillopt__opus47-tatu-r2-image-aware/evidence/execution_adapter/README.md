# Execution adapter snapshot

`executor_api.py` and `run_frozen_skill.py` are the exact local adapter files used for this submission. The added `--task-root` path allows the prepared group-2 task to use the same BenchmarkExecutor path as the original task while validating that the override contains `task.md`, `environment/`, and `verifier/`. `test_frozen_task_root.py` covers the override behavior; the relevant adapter suite passed 14 tests.

The prepared task receipt is `group2_preparation_receipt.json`: `group_02`, 20 images, 40 scored fields, zero model calls during preparation.

Command pattern for the three generalization executions:

```bash
python scripts/run_frozen_skill.py \
  --task jpg-ocr-stat \
  --method skillopt \
  --run-id experiments/opus47-jpg-group2-final-trial-N-20261102 \
  --skill-bundle experiments/opus47-gold15-jpg-refresh-v3-20261025/methods/skillopt/jpg-ocr-stat/best_skill \
  --task-root runtime_tasks/jpg-group2-final-frozen-20261102/jpg-ocr-stat \
  --stage group2-final-trial-N
```

Provider/model selection and the 65-iteration cap are recorded in each run's `executor_request.json`; credentials are intentionally not included.

