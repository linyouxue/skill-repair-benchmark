# Quadrotor Outer-Loop Planning And Control Artifact Pipeline

## Purpose
Generate a verifier-aligned planned trajectory and outer-loop control signals for a quadrotor by building an end-to-end, constraint-gated workflow: discover environment contracts (paths, schemas, limits), plan a dynamically feasible reference (pos/vel/acc plus attitude and body-rate feedforward if required), validate feasibility, optionally simulate/score, then write artifacts and re-verify them at the exact expected locations.

## When to Use
Use this skill when a task requires producing trajectory/controller artifacts (often a 15-row desired state matrix) and passing strict per-timestep feasibility and/or tracking checks under a provided quadrotor model (motor/thrust limits, gravity, sample rate), and when the expected output paths are enforced by a test harness or verifier.

## Procedure
- 1) Discover the contract before coding or writing files (no irreversible actions).
- Locate where the environment defines: (a) sample rate/dt, (b) mass and gravity, (c) actuator/thrust limits, (d) required artifact names and output locations.
- Use repository discovery rather than assumptions: search for config files (for example "*params*.yaml", "*system*.yaml"), task READMEs, and test scripts that reference output paths or artifact filenames.
- Decision: If required output path(s) are not explicitly stated, stop and derive them from the harness entrypoint (the script that grades/runs) by inspecting how it locates outputs; do not invent "/root/..." paths.
- 2) Build the reference trajectory generator around constraints (method is a choice, constraints are not).
- Inputs: waypoints/segments, waypoint times (or durations), modes, and dt from discovered sample rate.
- Produce time-sampled desired signals at each timestep, minimally:
- position p(t), velocity v(t), acceleration a(t)
- plus any task-declared additional rows (commonly attitude/orientation and body rates).
- Planner choice rule (do not hard-mandate one):
- If the contract emphasizes continuity/jerk limits, prefer a quintic/minimum-jerk segment method.
- If only smoothness is required, cubic is acceptable, but keep the option to time-scale segments.
- If attitude is part of the required state (or needed for tight tracking), map desired acceleration to a physically consistent thrust direction and orientation (tilt-aware), and generate corresponding body-rate feedforward only if the downstream controller consumes it.
- 3) Implement the outer-loop position controller with explicit state handling and tilt-aware thrust.
- Maintain integral state explicitly; never use a mutable default. Provide a constructor like make_integral_state() that returns a fresh zero vector.
- Compute errors using a consistent sign convention and document it in code (avoid silent flips).
- Compute commanded acceleration a_cmd = a_des + feedback_terms, then compute thrust magnitude using the discovered mass and gravity and the current/desired attitude mapping required by the model (do not assume small angles unless verified).
- Checkpoint: clamp or reject commands only using discovered limits (never hard-coded numbers).
- 4) Feasibility gate on the planned trajectory (must pass before simulation and before writing final artifacts).
- Read limits from the discovered config/model (thrust min/max, accel bounds, rate bounds, etc.).
- Audit per timestep:
- max/min of each acceleration component and horizontal norm
- implied thrust (and tilt) feasibility if your model requires it
- body-rate magnitude if you output omega
- If any violation occurs: record the first violating timestep and channel, then apply ONE bounded fallback (next step) rather than ad hoc redesign.
- 5) Bounded fallback loop (one of these, then re-run Step 4; do not loop indefinitely).
- If acceleration/thrust violates limits: increase segment duration (time-scaling) for the violating segment(s) or apply a global time scale, then regenerate trajectory.
- If tracking is poor but trajectory is feasible: add the missing feedforward terms that the controller/model expects (for example, attitude/omega feedforward from a_des and yaw plan), then re-run minimal simulation/score.
- If tool/library assumptions fail (missing spline library, etc.): switch to a simpler interpolator available in the environment (linear + smoothing window) and compensate via longer durations; keep the same output schema.
- Stop condition: after one fallback application, if constraints still fail, escalate to method-level change (planner family or mapping), not parameter tweaking.
- 6) Write artifacts to verifier-visible paths and verify them in-place (final gate).
- Write outputs ONLY to the exact discovered required path(s) and filenames.
- Immediately verify:
- existence and readability at those exact paths (list directory and stat files)
- reload/parsing succeeds using the same mechanism the environment uses (for example, load array file; parse JSON)
- shape/fields match the discovered schema (for example, 15 rows and expected length; required keys present)
- If writing fails (permissions/mounts): inspect the discovered output root and harness expectations; do not silently redirect to a different directory.

## Constraints / Pitfalls
- Never hard-code absolute output paths, numeric physical limits, sample rate, or schema details unless they are verified invariants in the discovered environment; always discover from config/harness and then enforce via a final existence+reload check at the exact required path.
- Do not commit to a single planner method (for example, cubic splines) as a rule. The invariant is constraint satisfaction (per-timestep feasibility) and required signal continuity; if feasibility fails, prefer time-scaling and limit-aware regeneration before controller retuning.