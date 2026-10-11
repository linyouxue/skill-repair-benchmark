# Complete experiment-record index

## Scope

`submission.json` is only an evaluator-facing final payload. It does **not** by
itself contain every optimization attempt. A complete handoff consists of this
submission directory plus both run directories:

- `../gpt52-31-skillopt-gpt52-ai360-20261011/`
- `../opus47-15-skillopt-opus47-tatu-20261008/`

The current GPT export contains all 31 configured tasks: 27 are strictly
healthy and 4 retain unhealthy status. The Opus export contains the requested
15 tasks and all 15 are healthy. Do not treat the combined top-level
`submission.json` as input to a single-version evaluator; each track has its
own payload under `outputs/`. Per-task health is recorded separately in each
track's `run_status.json`, because health fields are not part of the evaluator
submission schema.

## Where each requested record is stored

Paths below are relative to a run directory. Replace `<task>`, `<round>`, and
`<rollout>` with the values for a particular task and gate execution.

| Requested evidence | Record location and interpretation |
|---|---|
| Original failed execution received by the optimizer | `baseline/<task>/` and `jobs/baseline-original-skill/`; the evidence actually assembled for a repair round is recorded in `methods/skillopt/<task>/workspace/round_<round>/evidence_bundle.json`. |
| Independent diagnosis candidates | `methods/skillopt/<task>/workspace/round_<round>/diagnosis_samples/sample_*.json` (`N=3`). |
| Merged diagnosis and unselected alternatives | `.../round_<round>/diagnosis.json` and `diagnosis_raw.json`; the merged diagnosis records selected and unselected skill targets. |
| Add/delete/modify proposals and application results | `.../round_<round>/rewrite_raw/*.json`; `edits`, `edit_reports`, `applied_count`, `update_mode`, reasoning, and model usage are preserved. |
| Candidate Skill package actually validated | `jobs/skillopt/<rollout>/inputs/skills/`. The copied package is the exact candidate given to that execution. Request/config records include its digest. |
| Candidate execution and verifier result | `.../round_<round>/gate_result.json` points to `<rollout>` and records score, pass/comparability, errors, model and accounting. Full raw execution data is in `jobs/skillopt/<rollout>/`, including `trajectory/`, `agent/`, `trainer/`, `verifier/`, `executor_request.json`, `config.json`, `result.json`, and `benchmark_result.json`. |
| Accepted/rejected candidate and reason | `methods/skillopt/<task>/workspace/repair_loop.json`: every round has a `decision`; `rejected_buffer` stores rejected proposals, their rejection reason and edit reports. |
| Cross-round updates | `repair_loop.json` records accumulated failure-evidence and rejected-buffer sizes. Each `round_<round>/` preserves that round's evidence, diagnoses, proposal and validation result. |
| Initial, final and selected Skill versions | `before_skill/`, `after_skill/`, and `best_skill/`; `diff.patch` is the selected final difference. |
| Final version-to-execution mapping | `method_result.json`, `rollout_pointer.json`, and the selected round in `repair_loop.json`. The exported per-track submission uses the selected result's actual `rollout_id` as `executor_run_id`. |
| Commands and configuration | `commands/`, `metadata.json`, `source_manifest.json`, run `README.md`, plus each rollout's `config.json`, `executor_request.json`, and `prompts.json`. Credentials remain external in `.env` and must not be packaged. |
| Terminal history and infrastructure failures | `logs/terminal-*.log`. These retain timestamps and error text. Per the experiment instruction, partial directories from unhealthy infrastructure/API attempts are deleted before rerun and therefore are not represented as candidate Skill packages. |

The linkage chain for a candidate is:

```text
task + round
  -> workspace/round_<round>/rewrite_raw/*.json
  -> workspace/round_<round>/gate_result.json (`rollout_id`, `rollout_dir`)
  -> jobs/skillopt/<rollout>/inputs/skills/ and raw execution/verifier files
  -> workspace/repair_loop.json (`decision`, rejection reason)
  -> method_result.json / rollout_pointer.json (final selection)
```

## Train, validation, and final-test use

There is no independent train/validation/test task split in these runs.

- The source failed trajectory for a task is the optimization evidence.
- Diagnosis and rewriting operate per task.
- Each proposed Skill is gated by executing that **same task**.
- The selected gate result is also the result reported for that task.

Consequently, selection has same-task leakage and is not a held-out validation
estimate. This is explicitly recorded by `same_task_gate` and
`same_task_gate_leakage` in each `repair_loop.json` and `method_result.json`.
No separate validation set was configured or used.

## Enabled and retained status

- Intermediate diagnosis candidates: enabled and retained.
- Edit proposals and edit-application reports: enabled and retained.
- Candidate gate executions and validation results: enabled and retained.
- Acceptance/rejection decisions and rejected-candidate buffer: enabled and
  retained when a candidate reached the gate.
- Cross-round feedback: enabled; failed-gate evidence and rejected proposals
  feed later rounds and are recorded in `repair_loop.json`.
- Held-out validation set: not enabled.
- Exact assembled optimizer input as one standalone verbatim prompt file: not
  separately retained. Its source evidence, context metadata, optimizer output,
  and usage are retained, but the exact request body may require reconstruction.
- Infrastructure-invalid partial attempts: intentionally not retained as full
  candidate directories; they are removed before rerun. Corresponding terminal
  error records remain in `logs/`.

## Public inputs and code version

- GPT baseline archive: <https://github.com/linyouxue/skill-repair-benchmark/tree/main/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916>
- Opus baseline archive: <https://github.com/linyouxue/skill-repair-benchmark/tree/main/evaluation/results/Opus47-OriginalSkill-79Tasks-20260920>
- Upstream task packages: <https://github.com/benchflow-ai/skillsbench/tree/main/tasks> and <https://github.com/benchflow-ai/skillsbench/tree/main/tasks-extra>
- Baseline source archive commit: `c3159e6f805ab23dd3f911c4c12d7beef9c6d09c`

Local adapter/runner changes and the exact source copies are identified by each
track's `source_manifest.json`; reproducible launch commands are in each
track's `commands/` directory.
