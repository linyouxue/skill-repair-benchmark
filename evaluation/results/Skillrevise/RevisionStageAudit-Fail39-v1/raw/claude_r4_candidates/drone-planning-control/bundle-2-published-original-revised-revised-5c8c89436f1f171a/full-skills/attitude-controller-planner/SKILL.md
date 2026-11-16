# Attitude Inner Loop: Demand-Sized Gains and Verified Rollout

## Purpose
Guide sizing and verification of a quadrotor attitude inner loop (planner from desired lateral acceleration to desired tilt, plus PID on Euler error) so that attitude bandwidth is set from trajectory demand and the observable per-timestep tracking budget, not from reactive retuning.

## When to Use
Use when implementing or tuning the attitude planner/PID inside an end-to-end quadrotor tracking pipeline where acceptance is judged by per-command position error against a task-declared budget. For position-loop structure, trajectory generation, motor mixing, and artifact schemas, consult the sibling skills; this skill still runs the final verification check across those layers.

## Procedure
- Discover contract: read the task spec to extract the per-timestep position error budget and allowed tilt error delta_theta. If absent, inspect the verifier/trace for the smallest observed failing max_err and use that as the budget; log the chosen value.
- Pre-run sizing: compute a_peak = max |a_lat| across the planned trajectory. Set kp_att[x,y] such that sqrt(kp_att) >= 2 * a_peak / (g * delta_theta), and kd_att[x,y] = 2 * zeta * sqrt(kp_att) with zeta near 0.7. Yaw gains lower; ki zero unless step 4 shows sustained bias.
- Short dry run: simulate one representative fly command plus one hover; create integral state as zeros(3) fresh per run; derive dt from params['sample_rate'].
- Verify and escalate (bounded): assert per-command max position error < budget. If any fly command fails, raise kp_att,kd_att by ~1.5x (max 3 iterations) before touching position-loop gains; if steady-state Euler error persists on one axis, add small ki on that axis only.

## Constraints / Pitfalls
- Never store integral state in a mutable default argument; never hardcode dt, sample rate, inertia, gains, or the tracking budget.
- Do not claim completion from self-reported PASS alone; the final verification must compare per-command max_err to the discovered budget, and escalation must be bounded to avoid gain thrash.