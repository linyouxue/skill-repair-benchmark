# Verifier-Aligned Quadrotor Inner-Loop Integration (Attitude Planning + Control)

## Purpose
Integrate or revise an attitude planner and attitude controller inside a larger quadrotor stack in a way that matches the repository's actual interfaces, output artifacts, and official verifier expectations, with explicit discovery, bounded fallbacks, and final schema/path validation.

## When to Use
Use this skill when a task requires implementing or modifying quadrotor attitude planning/control as part of an end-to-end pipeline that is evaluated by a provided script/verifier (simulation, tracking, and artifact generation). Do not use it for standalone control-theory discussion or when no executable evaluation exists.

## Procedure
- 1) Discover the ground truth environment contract (before coding)
- Locate the primary entrypoint(s): search the repo for evaluation/verifier scripts, CI commands, or README instructions (for example: files named like evaluate*, verify*, grade*, test*, or a Makefile/pyproject task).
- Identify the controller/planner call sites and data models by reading the code where they are invoked:
- How state is represented (Euler/quaternion/rotation matrix), and how angular velocity is represented (body rates vs Euler rates).
- How parameters are provided (dataclass/object vs dict), and where dt comes from.
- Checkpoint: write down (in your own notes) the exact function signatures and the exact artifact outputs (filenames/paths) the verifier expects. If unknown, mark as unknown and proceed to step 2 to discover via running help/usage.
- 2) Establish a runnable verifier loop (execution anchor)
- Try to run the official verifier/evaluation command exactly as provided by the repo/task docs.
- If it fails due to missing command/script, take one bounded fallback:
- Search for the closest evaluation entrypoint (tests, examples, or a script that produces the scored artifacts), then run its smallest smoke mode (short horizon, minimal scenario) if available.
- Checkpoint: you must have a repeatable command that produces observable pass/fail output (even if currently failing) before making major control changes.
- 3) Implement attitude planning using discovered frames and interfaces (no hardcoded API assumptions)
- Implement the planner to produce whatever the repo expects (desired attitude and optionally desired body rates):
- If the stack uses Euler angles, verify the mapping between body rates and Euler angle rates; do not assume omega = [0, 0, yaw_rate] unless the call site explicitly defines desired omega that way.
- If the stack uses quaternions/rotation matrices, compute attitude error in that representation rather than forcing Euler math.
- Decision point: feedforward rates
- If the desired attitude is time-parameterized or comes from a trajectory with derivatives, compute/approximate desired body rates consistently.
- Otherwise, set missing feedforward components to zero only if the downstream controller is designed to operate without them (confirmed in the code).
- 4) Implement the attitude controller with saturation-aware state and reset rules
- Use the repo's chosen error definition (Euler error or SO(3) error). Do not substitute a different error metric unless you also update all dependent kinematics consistently.
- Maintain integrator state explicitly (no mutable defaults) and reset/limit it when any of these are true (based on what the repo models):
- Actuator/moment/thrust saturation occurs.
- Mode switches, episode reset, or large setpoint discontinuities occur.
- Compute dt only from discovered parameters (for example, params.dt or a timestep in the simulator), not from assumed keys.
- 5) Validate outputs and schemas at verifier-visible paths (execution anchor)
- If the pipeline writes artifacts (trajectories, logs, JSON/NPZ/CSV), locate the exact output directory/file names used by the evaluation.
- After generating artifacts, reload them in the same runtime and assert minimal schema properties derived from the repo/task declarations:
- Required keys exist.
- Types are correct (numbers vs arrays/objects).
- Shapes/lengths are consistent (for example, number of timesteps matches produced rollout length).
- Checkpoint: fail fast if any artifact cannot be reloaded or required keys are missing; fix before rerunning the verifier.
- 6) Final verifier run and stop condition (execution anchor)
- Run the official verifier/evaluation command again with no manual edits between artifact generation and verification.
- Only claim completion when:
- The verifier reports pass (or meets its published threshold), and
- The artifact existence/readability and schema reload checks pass at the exact verifier-consumed paths.

## Constraints / Pitfalls
- Do not hardcode parameter access patterns, dt, file paths, or planner/controller output fields. Every such assumption must be confirmed by reading the repo call sites or configs first; otherwise add a discovery step or a small adapter layer.
- Do not declare success based on local plots or ad hoc checks. The only completion signal is a passing official verifier (or closest repo-provided evaluation) plus a final artifact path + schema reload validation at the verifier-visible locations.