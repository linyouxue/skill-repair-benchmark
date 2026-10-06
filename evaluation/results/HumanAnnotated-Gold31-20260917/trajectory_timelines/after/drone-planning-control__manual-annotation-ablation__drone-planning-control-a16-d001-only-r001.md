# drone-planning-control — Execution Timeline (after)

> Readable ablation index over `acp_trajectory.jsonl`. Agent-thought bodies are omitted; the raw JSONL remains the source of truth.

## Run metadata

| Field | Value |
|---|---|
| Task | drone-planning-control |
| Method | manual-annotation-ablation |
| Run ID | drone-planning-control-a16-d001-only-r001 |
| Condition | method-skill |
| Before/After | after |
| Model | openrouter/openai/gpt-5.2 |
| Protocol | skillrepair-v1 |
| Protocol version | 2 |
| Execution OK | true |
| Task passed | false |
| Outcome | FAIL |
| Reward | 0.533333 |
| Agent iterations | 27 |
| Provider requests | 27 |
| Wall time (s) | 811.9 |
| Cost (USD) | 0.59156265 |
| Termination reason | end_turn |
| Trajectory source | acp |
| Partial trajectory | false |
| Tool-call steps | 25 |
| Raw ACP events | 31 |
| Trajectory bytes | 127290 |
| Trajectory empty | false |

## Event summary

### ACP event types

| Event type | Count |
|---|---:|
| `agent_iteration_outcome` | 1 |
| `agent_message` | 2 |
| `agent_thought` | 2 |
| `tool_call` | 25 |
| `user_message` | 1 |

### Tool-call kinds

| Kind | Count |
|---|---:|
| `execute` | 14 |
| `edit` | 5 |
| `read` | 4 |
| `other` | 2 |

## Selected observable milestones

- The agent inspected all command patterns and system parameters, then implemented a fresh simulation/tuning stack.
- The tuning implementation used a finite local gain search and, when no candidate passed, still retained a best-so-far candidate as final output.
- The final internal artifact check was executed, but the official benchmark result remained `reward=0.533333` (16/30 commands).
- This run therefore documents an adherence failure of the first unified D001 wording rather than evidence that the historical D003/D004 defects are necessary.

## Final outcome

- **Outcome:** `FAIL`
- **Execution OK:** `true`
- **Task passed:** `false`
- **Reward:** `0.533333`

## Raw evidence

- ACP trajectory: `tasks/drone-planning-control/ablation_runs/drone-planning-control-a16-d001-only-r001/trajectory/acp_trajectory.jsonl`
- `benchmark_result.json`
- `executor_request.json`
- `result.json`

_This Markdown is a readable index over the raw rollout evidence._
