# drone-planning-control — Execution Timeline (after)

> Readable ablation index over `acp_trajectory.jsonl`. Agent-thought bodies are omitted; the raw JSONL remains the source of truth.

## Run metadata

| Field | Value |
|---|---|
| Task | drone-planning-control |
| Method | manual-annotation-ablation |
| Run ID | drone-planning-control-a16-d001-v4-r001 |
| Condition | method-skill |
| Before/After | after |
| Model | openrouter/openai/gpt-5.2 |
| Protocol | skillrepair-v1 |
| Protocol version | 2 |
| Execution OK | true |
| Task passed | true |
| Outcome | PASS |
| Reward | 1.0 |
| Agent iterations | 36 |
| Provider requests | 36 |
| Wall time (s) | 791.9 |
| Cost (USD) | 0.7807121 |
| Termination reason | end_turn |
| Trajectory source | acp |
| Partial trajectory | false |
| Tool-call steps | 34 |
| Raw ACP events | 40 |
| Trajectory bytes | 140391 |
| Trajectory empty | false |

## Event summary

### ACP event types

| Event type | Count |
|---|---:|
| `agent_iteration_outcome` | 1 |
| `agent_message` | 2 |
| `agent_thought` | 2 |
| `tool_call` | 34 |
| `user_message` | 1 |

### Tool-call kinds

| Kind | Count |
|---|---:|
| `execute` | 15 |
| `edit` | 15 |
| `read` | 1 |
| `other` | 3 |

## Selected observable milestones

- The agent kept the unified per-command hard gate and staged gain search: a candidate had to satisfy all task hard criteria before selection, followed by a clean rerun and a final all-command sweep.
- Experimental controls removed the v3 reproducibility confounds: clamped cubic trajectory planning, literal position-controller formula without extra acceleration clipping, zero hidden initial state, simplified benchmark plant, and canonical saved-trajectory semantics.
- The final internal sweep reported no failed commands, and the official verifier independently accepted all 30 commands.
- Official result: `PASS`, `reward=1.0`. This is the clean F→P ablation supporting the final structured Gold decision `defect_sets = [["D001"]]`.

## Final outcome

- **Outcome:** `PASS`
- **Execution OK:** `true`
- **Task passed:** `true`
- **Reward:** `1.0`

## Raw evidence

- ACP trajectory: `tasks/drone-planning-control/ablation_runs/drone-planning-control-a16-d001-v4-r001/trajectory/acp_trajectory.jsonl`
- `benchmark_result.json`
- `executor_request.json`
- `result.json`

_This Markdown is a readable index over the raw rollout evidence._
