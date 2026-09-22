# Batch Diagnoses

## Task dynamic-object-aware-egomotion (reward: 0.0)

<label>Missing output file generation</label>

(1) First observable failure:
- The run produced **no outputs at all**: output inventory is empty, so `/root/pred_instructions.json` and `/root/pred_dyn_masks.npz` were not created.

(2) Trajectory step that produced it:
- This failure occurs at the **finalization/output-writing step** of the agent trajectory (i.e., after any analysis), where the agent should serialize results and write the two required files. The trace/evidence available indicates the run ended without writing artifacts (no saved files recorded).

(3) Relevant skill rule or missing rule:
- **Missing/insufficient “always write required artifacts” rule** for this task type: the skill should enforce that, regardless of analysis quality, it must (a) create a valid JSON mapping of sampled frame intervals to one of the allowed motion labels, and (b) create a valid NPZ with `shape` and per-frame CSR keys (`f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr`) for every sampled frame at fps=5.
- This is a **skill-controllable** failure (not an API/permission/harness/grader issue): the environment executed, but the agent did not emit the mandated files.

(4) General corrective behavior:
- Add/strengthen a mandatory “deliverables gate” behavior: before ending, the agent must:
  1) Compute the sampled frame indices at fps=5 and ensure intervals cover all sampled frames with half-open `"i->i+1"` keys.
  2) Always write `/root/pred_instructions.json` with only valid labels.
  3) Always write `/root/pred_dyn_masks.npz` including `shape=[H,W]` and CSR triplets for every sampled frame (even if masks are empty, store valid empty CSR arrays).
  4) Verify on-disk existence and basic loadability of both files, and only then terminate.

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/iter_0/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/iter_0/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/workspace
