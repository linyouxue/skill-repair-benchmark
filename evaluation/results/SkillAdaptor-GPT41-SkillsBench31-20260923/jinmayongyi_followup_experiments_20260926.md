# jinmayongyi follow-up experiment plan

The GPT-5.2 representative input trajectories are complete (31 tasks). The
existing repaired replay is also complete (31 healthy runs, 3 passes), but its
diagnosis/repair model is GPT-4.1 because GPT-5.2 returned HTTP 429 through the
previous gateway. This file records the requested follow-up configurations;
credentials are intentionally not stored here.

Use `configs/jinmayongyi_followup_experiments_20260926.json` as the source of
truth. Run diagnosis/repair with three workers where the model context is
process-local, and run each repaired task up to three times. Preserve every
attempt and accept a task if any healthy verifier run passes. A provider,
container, or verifier startup failure is not a task failure and must be retried
after the cause is recorded. A healthy verifier failure may also be retried for
the requested randomness robustness analysis, but all attempts remain visible.

The Claude mapping is `anthropic/claude-opus-4.7` on OpenRouter, temperature 1,
high effort, thinking disabled, and 32,768 output tokens. The GPT-5.2 mapping is
`openai/gpt-5.2`, high effort, thinking enabled, temperature/top-p 1, tool calls
parallel, and non-streaming. The execution cap is 60 iterations; GPT-5.2 has a
3600-second request timeout and 21600-second total timeout.

No follow-up live run was started on 2026-09-26 because `OPENROUTER_API_KEY` was
not present in the process environment. Running without it would produce no
valid experiment evidence.
