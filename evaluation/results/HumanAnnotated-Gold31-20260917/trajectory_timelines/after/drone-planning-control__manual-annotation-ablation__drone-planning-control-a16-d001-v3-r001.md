# drone-planning-control — Execution Timeline (after)

> Readable ablation index over `acp_trajectory.jsonl`. Agent-thought bodies are omitted; the raw JSONL remains the source of truth.

## Run metadata

| Field | Value |
|---|---|
| Task | drone-planning-control |
| Method | manual-annotation-ablation |
| Run ID | drone-planning-control-a16-d001-v3-r001 |
| Condition | method-skill |
| Before/After | after |
| Model | openrouter/openai/gpt-5.2 |
| Protocol | skillrepair-v1 |
| Protocol version | 2 |
| Execution OK | true |
| Task passed | false |
| Outcome | FAIL |
| Reward | 0.566667 |
| Agent iterations | 30 |
| Provider requests | 30 |
| Wall time (s) | 1140.6 |
| Cost (USD) | 0.69649825 |
| Termination reason | end_turn |
| Trajectory source | acp |
| Partial trajectory | false |
| Tool-call steps | 28 |
| Raw ACP events | 34 |
| Trajectory bytes | 136729 |
| Trajectory empty | false |

## Event summary

### ACP event types

| Event type | Count |
|---|---:|
| `agent_iteration_outcome` | 1 |
| `agent_message` | 2 |
| `agent_thought` | 2 |
| `tool_call` | 28 |
| `user_message` | 1 |

### Tool-call kinds

| Kind | Count |
|---|---:|
| `execute` | 14 |
| `edit` | 13 |
| `read` | 1 |

## Selected observable milestones

- The agent explicitly implemented the simplified plant equations `rot_dot = omega` and `omega_dot = I^-1 M`, while keeping a blocking per-command hard gate.
- Its own full pipeline and final sweep reported all 30 commands passing the local hard checks.
- The official verifier accepted only 17/30 (`reward=0.566667`), exposing a reproducibility mismatch rather than a failure to execute the hard gate.
- Later audit traced the remaining mismatch to other execution-model choices such as planner/controller/initial-state/trajectory-recording conventions; this run therefore does not support restoring historical D004 as a scoring requirement.

## Final outcome

- **Outcome:** `FAIL`
- **Execution OK:** `true`
- **Task passed:** `false`
- **Reward:** `0.566667`

## Raw evidence

- ACP trajectory: `tasks/drone-planning-control/ablation_runs/drone-planning-control-a16-d001-v3-r001/trajectory/acp_trajectory.jsonl`
- `benchmark_result.json`
- `executor_request.json`
- `result.json`

_This Markdown is a readable index over the raw rollout evidence._
