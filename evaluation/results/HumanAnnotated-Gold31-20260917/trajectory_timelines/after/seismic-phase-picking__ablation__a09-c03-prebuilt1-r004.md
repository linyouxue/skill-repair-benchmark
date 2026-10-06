# seismic-phase-picking — Execution Timeline (after)

> Readable ablation index over `acp_trajectory.jsonl`. Agent-thought bodies are omitted; the raw JSONL remains the source of truth.

## Run metadata

| Field | Value |
|---|---|
| Task | seismic-phase-picking |
| Method | ablation |
| Stage | A09/C03 |
| Run ID | a09-c03-prebuilt1-r004 |
| Condition | method-skill |
| Before/After | after |
| Model | openrouter/openai/gpt-5.2 |
| Protocol | skillrepair-v1 |
| Protocol version | 1 |
| Execution OK | true |
| Task passed | false |
| Outcome | FAIL |
| Reward | 0.0 |
| Agent iterations | 51 |
| Provider requests | 51 |
| Wall time (s) | 1058.4 |
| Cost (USD) | 1.2331039 |
| Termination reason | end_turn |
| Trajectory source | acp |
| Partial trajectory | false |
| Tool-call steps | 50 |
| Raw ACP events | 54 |
| Trajectory bytes | 282547 |
| Trajectory empty | false |
| Harness comparison status | diagnostic-non-comparable |

## Event summary

### ACP event types

| Event type | Count |
|---|---:|
| `agent_iteration_outcome` | 1 |
| `agent_message` | 1 |
| `agent_thought` | 1 |
| `tool_call` | 50 |
| `user_message` | 1 |

### Tool-call kinds

| Kind | Count |
|---|---:|
| `execute` | 50 |

## Selected observable milestones

- The agent inspected all 100 NPZ traces, channel metadata, sampling intervals, and available SeisBench/ObsPy models.
- It built a PhaseNet-based picker around probability thresholds, local peak extraction and phase-specific filtering, and regenerated `/root/results.csv` several times while adjusting thresholds/fallback behavior.
- The final artifact contained 198 predictions. Official verifier metrics were: P precision/recall/F1 = 0.730/0.730/0.730; S precision/recall/F1 = 0.571/0.560/0.566.
- Official threshold tests: P >=0.7 passed; S >=0.6 failed. Final result therefore remained FAIL.
- The trajectory also shows an unsupported fixed P→S timing rule being introduced during implementation, so the run is evidence that the C03 atom alone does not establish sufficiency; it is not evidence for deleting the other seismic Gold mechanisms.

## Final outcome

- **Outcome:** `FAIL`
- **Execution OK:** `true`
- **Task passed:** `false`
- **Reward:** `0.0`
- **P-wave F1:** `0.730` (required `>=0.700`)
- **S-wave F1:** `0.566` (required `>=0.600`)

## Raw evidence

- ACP trajectory: `tasks/seismic-phase-picking/ablation_runs/a09-c03-prebuilt1-r004/trajectory/acp_trajectory.jsonl`
- Verifier stdout: `tasks/seismic-phase-picking/ablation_runs/a09-c03-prebuilt1-r004/verifier/test-stdout.txt`
- `benchmark_result.json`
- `executor_request.json`
- `result.json`

_This Markdown is a readable index over the raw rollout evidence._
