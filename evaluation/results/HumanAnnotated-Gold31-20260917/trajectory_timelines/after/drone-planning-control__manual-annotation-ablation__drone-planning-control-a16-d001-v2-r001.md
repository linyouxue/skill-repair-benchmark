# drone-planning-control — Execution Timeline (after)

> Readable ablation index over `acp_trajectory.jsonl`. Agent-thought bodies are omitted; the raw JSONL remains the source of truth.

## Run metadata

| Field | Value |
|---|---|
| Task | drone-planning-control |
| Method | manual-annotation-ablation |
| Run ID | drone-planning-control-a16-d001-v2-r001 |
| Condition | method-skill |
| Before/After | after |
| Model | openrouter/openai/gpt-5.2 |
| Protocol | skillrepair-v1 |
| Protocol version | 2 |
| Execution OK | true |
| Task passed | true |
| Outcome | PASS |
| Reward | 1.0 |
| Agent iterations | 34 |
| Provider requests | 34 |
| Wall time (s) | 1168.1 |
| Cost (USD) | 0.7877618 |
| Termination reason | end_turn |
| Trajectory source | acp |
| Partial trajectory | false |
| Tool-call steps | 32 |
| Raw ACP events | 39 |
| Trajectory bytes | 145256 |
| Trajectory empty | false |

## Event summary

### ACP event types

| Event type | Count |
|---|---:|
| `agent_iteration_outcome` | 1 |
| `agent_message` | 2 |
| `agent_thought` | 3 |
| `tool_call` | 32 |
| `user_message` | 1 |

### Tool-call kinds

| Kind | Count |
|---|---:|
| `execute` | 17 |
| `edit` | 15 |

## Selected observable milestones

- The agent implemented a hard-gated tuning loop: a non-passing candidate could not be returned as final, and selected gains were rerun from a clean state before saving.
- It performed an explicit all-command validation sweep and found no failing commands in its generated artifacts.
- The official benchmark result was `PASS`, `reward=1.0`, with all 30 commands accepted.
- The implementation also used fuller rigid-body dynamics, so this run establishes a fresh F→P path for the unified hard-gated tuning mechanism but is not by itself a clean test of the historical D004 plant restriction.

## Final outcome

- **Outcome:** `PASS`
- **Execution OK:** `true`
- **Task passed:** `true`
- **Reward:** `1.0`

## Raw evidence

- ACP trajectory: `tasks/drone-planning-control/ablation_runs/drone-planning-control-a16-d001-v2-r001/trajectory/acp_trajectory.jsonl`
- `benchmark_result.json`
- `executor_request.json`
- `result.json`

_This Markdown is a readable index over the raw rollout evidence._
