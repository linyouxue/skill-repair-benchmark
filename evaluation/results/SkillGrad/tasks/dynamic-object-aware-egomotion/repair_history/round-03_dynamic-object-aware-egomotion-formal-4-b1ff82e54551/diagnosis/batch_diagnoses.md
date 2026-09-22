# Batch Diagnoses

## Task dynamic-object-aware-egomotion (reward: 0.0)

<label>Missing required output artifacts</label>

(1) First observable failure:
- No required deliverables were produced on disk. The output inventory contains only the input video, and the run ended with reward 0 while `execution_ok: true`, which is consistent with the verifier failing to find `/root/pred_instructions.json` and `/root/pred_dyn_masks.npz` (or finding them malformed/empty).

(2) Trajectory step that produced it:
- The final agent termination (“end_turn”) occurred without any preceding steps that run sampling/egomotion/mask generation and, critically, without writing the two required files to the specified absolute `/root/...` paths. This is the first point at which the failure becomes inevitable.

(3) Relevant skill rule or missing rule:
- Relevant: `output-validation` skill’s “Deliverables gate (hard stop)” explicitly requires: write JSON + NPZ unconditionally, then re-open from disk and validate existence/loadability/key coverage before terminating.
- The run shows `n_skill_invocations: 0`, so the agent did not apply that gate. This is a skill-controllable planning/compliance failure, not an API/dependency issue.

(4) General corrective behavior:
- Before finishing, always execute a complete pipeline that (a) samples frames at the required FPS, (b) computes interval motion labels, (c) builds per-sampled-frame dynamic-object masks, (d) writes both artifacts to the exact required absolute paths, and (e) re-loads them to verify existence, schema, and CSR integrity. Do not terminate until this deliverables gate passes, even if outputs are trivial (write “Stay” and empty masks rather than nothing).

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/iter_3/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/iter_3/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/workspace
