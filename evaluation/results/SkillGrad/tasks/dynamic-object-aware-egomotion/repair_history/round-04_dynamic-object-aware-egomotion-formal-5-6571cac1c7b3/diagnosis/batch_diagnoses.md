# Batch Diagnoses

## Task dynamic-object-aware-egomotion (reward: 0.0)

<label>Premature termination without artifacts</label>

  <first_observable_failure>
    The required output artifacts were never created on disk: neither <code>/root/pred_instructions.json</code> nor <code>/root/pred_dyn_masks.npz</code> exists (output inventory contains only <code>input.mp4</code>). This is the earliest externally observable failure because the verifier can only grade on-disk files.
  </first_observable_failure>

  <trajectory_step_that_produced_it>
    The final agent step that ended the turn (“end_turn” termination) occurred without running any pipeline that samples frames, estimates egomotion, builds CSR masks, and writes/validates deliverables. In the trace summary, there are tool calls but no evidence of writing outputs; the run terminates while outputs are still missing.
  </trajectory_step_that_produced_it>

  <relevant_skill_rule_or_missing_rule>
    This violates the <code>output-validation</code> skill’s “Deliverables gate (hard stop)”: 
    - “Write required artifacts unconditionally … Re-open from disk and validate … never terminate until this gate has executed and passed.”
    The corrective rule already exists but was not invoked/enforced. No new domain rule is needed; it’s a skill-execution/termination-control failure.
  </relevant_skill_rule_or_missing_rule>

  <general_corrective_behavior>
    Before terminating, always execute a deliverables gate: (1) compute sampled frame indices at fps=5, (2) produce per-sampled-frame motion labels and compress into <code>start-&gt;end</code> intervals covering all sampled frames, (3) generate a CSR triplet mask for every sampled frame and store <code>shape</code>, (4) write both files to the exact required absolute paths, and (5) reload both files to assert existence, key coverage, label validity, and CSR integrity. If any check fails, do not terminate; fix and re-write.
  </general_corrective_behavior>

  <error_type>
    Skill-controllable (agent failed to follow/enforce the provided output-validation termination gate), not an API/dependency/permission/grader issue.
  </error_type>

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/iter_4/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/iter_4/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/dynamic-object-aware-egomotion/workspace
