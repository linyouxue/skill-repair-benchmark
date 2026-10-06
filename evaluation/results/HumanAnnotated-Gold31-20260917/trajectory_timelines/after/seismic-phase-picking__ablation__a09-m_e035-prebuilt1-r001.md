# seismic-phase-picking — Execution Timeline (after)

> Readable ablation-control index over `acp_trajectory.jsonl`. Agent-thought bodies are omitted; the raw JSONL remains the source of truth.

## Run metadata

| Field | Value |
|---|---|
| Task | seismic-phase-picking |
| Method | ablation |
| Stage | A09/M_E035 |
| Run ID | a09-m_e035-prebuilt1-r001 |
| Condition | method-skill |
| Before/After | after |
| Model | openrouter/openai/gpt-5.2 |
| Protocol | skillrepair-v1 |
| Protocol version | 1 |
| Execution OK | true |
| Task passed | true |
| Outcome | PASS |
| Reward | 1.0 |
| Agent iterations | 24 |
| Provider requests | 24 |
| Wall time (s) | 881.4 |
| Cost (USD) | 0.58420985 |
| Termination reason | end_turn |
| Trajectory source | acp |
| Partial trajectory | false |
| Tool-call steps | 22 |
| Raw ACP events | 28 |
| Trajectory bytes | 170980 |
| Trajectory empty | false |
| Harness comparison status | diagnostic-non-comparable |

## Event summary

### ACP event types

| Event type | Count |
|---|---:|
| `agent_iteration_outcome` | 1 |
| `agent_message` | 2 |
| `agent_thought` | 2 |
| `tool_call` | 22 |
| `user_message` | 1 |

### Tool-call kinds

| Kind | Count |
|---|---:|
| `execute` | 22 |

## Selected observable milestones

- This is the historical `M_E035` successful-control arm used next to the C03 screen.
- The agent inspected channel naming/coverage and data amplitudes, handled incomplete channel metadata, scaled extremely small traces, and generated PhaseNet/EQTransformer-backed picks into `/root/results.csv`.
- Official verifier loaded 183 predictions and accepted all four threshold tests.
- Official metrics: P precision=0.902, recall=0.830, F1=0.865; S precision=0.747, recall=0.680, F1=0.712.
- The control therefore demonstrates that the current frozen task/model route can still achieve a PASS, while the C03-only screen remains insufficient.

## Final outcome

- **Outcome:** `PASS`
- **Execution OK:** `true`
- **Task passed:** `true`
- **Reward:** `1.0`
- **P-wave F1:** `0.865`
- **S-wave F1:** `0.712`

## Raw evidence

- ACP trajectory: `tasks/seismic-phase-picking/ablation_runs/a09-m_e035-prebuilt1-r001/trajectory/acp_trajectory.jsonl`
- Verifier stdout: `tasks/seismic-phase-picking/ablation_runs/a09-m_e035-prebuilt1-r001/verifier/test-stdout.txt`
- `benchmark_result.json`
- `executor_request.json`
- `result.json`

_This Markdown is a readable index over the raw rollout evidence._
