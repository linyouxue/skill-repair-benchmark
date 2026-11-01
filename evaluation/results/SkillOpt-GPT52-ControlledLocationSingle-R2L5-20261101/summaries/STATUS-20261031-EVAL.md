# GPT-5.2 controlled R2L5 evaluation status — 2026-10-31

- Repair candidates: 22/22 complete
- Candidate metadata: 22/22 record N=3, L=5, R=2, two rounds
- Prepared evaluator inputs: 22/22
- Valid native evaluations: 1/22
- Valid pass/fail/error: 1/0/0
- Current active unit: location-data-to-d3
- Evaluation model: ai360/openai/gpt-5.2
- Evaluation reasoning effort: medium

Valid result:

- location-dialogue-parser: pass, reward 1.0, 177813 tokens,
  11 tool calls; skill preload digest matched.

Infrastructure-invalid attempts retained for audit and excluded from formal
task outcomes:

- rep-001: Docker daemon was not running; zero model calls/tokens.
- dialogue rep-002: task-image apt install timed out; zero model calls.
- dialogue rep-003: image lacked curl for the LiteLLM reachability probe;
  zero model calls.
- dialogue rep-004: OpenHands implicit reasoning_effort=high was rejected
  by AI360 GPT-5.2, which supports medium.
- dialogue rep-005: explicit effort was recorded but the ACP layer attempted
  an unsupported config option before execution; zero model calls.

Shared evaluator fixes were verified before resumption: OpenHands installation
no longer depends on task-image apt, the LiteLLM probe falls back to Python
when curl is absent, and explicit OpenHands effort is passed through its
launch environment. The batch worker skips only successful BenchFlow exits and
writes fresh numbered attempts without overwriting evidence.
