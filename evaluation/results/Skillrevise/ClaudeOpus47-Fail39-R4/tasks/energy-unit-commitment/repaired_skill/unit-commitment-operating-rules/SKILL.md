# Unit Commitment Operating Rules

## Purpose
Produce a day-ahead or multi-period unit commitment schedule (commitment, dispatch, reserve, costs) that passes the task's external verifier, not just internal self-checks.

## When to Use
Task supplies generators, demand, reserve requirement, and operating constraints across T periods and asks for a schedule plus feasibility/cost report. Do not use for single-period economic dispatch.

## Procedure
- Discover environment: list the task directory; read the input file and print its top-level keys and per-resource field names; locate any output path, report schema, or verifier/acceptance script. Do not assume field names, hour indexing, or MW convention.
- Probe solver availability in order (pulp, pyomo, scipy.optimize.milp); record which is used. If none supports MILP, fall back to a documented heuristic and flag it in the report.
- Pick one production convention (actual MW vs above-minimum) and apply it consistently across capacity, ramping, reserve deliverability, cost, and reporting. Convert at output boundary to whatever the input/verifier uses.
- Build MILP with: u/start/stop binaries; transition identity u[t]-prev_u == start-stop; joint `production + reserve <= pmax*u` (and startup/shutdown capability when startup_limit/shutdown_limit fields exist); ramping with prev set to initial output at t=0; min up/down windows that account for pre-horizon on/off duration; startup cost chosen by largest tier lag <= offline_duration only if the data encodes lags that way, otherwise match the field name observed in step 1.
- After writing the report, reload it and independently recompute every constraint from the input: demand balance, reserve sum, per-unit capacity with u, offline zeros, transition identity, min up/down, ramping, deliverability, cost. Set each `constraint_check` to 'pass' only if its numeric residual is within tol; otherwise record the residual and do not label 'pass'.
- If a verifier/acceptance script was discovered, run it against the written report and iterate on failures before finalizing. If none exists, keep residuals in the report rather than fabricating 'pass'.

## Constraints / Pitfalls
- Do not set any `constraint_check` to 'pass' without a numeric recomputation from the written arrays vs the input file.
- Do not hard-code paths, field names, hour base (0 vs 1), or startup-tier semantics; derive them from step 1.
- Reserve only from online thermal units; never from renewable headroom unless input explicitly permits.
- First-period ramping and min up/down must use initial output and initial on/off duration from the input.
- Keep one MW convention end-to-end; mismatched conventions silently break deliverability and cost.
- If internal checks pass but the external verifier fails, re-run step 1 to recheck schema and output-path assumptions before re-solving.