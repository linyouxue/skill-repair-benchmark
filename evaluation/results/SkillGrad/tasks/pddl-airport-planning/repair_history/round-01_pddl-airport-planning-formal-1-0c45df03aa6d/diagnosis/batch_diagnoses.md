# Batch Diagnoses

## Task pddl-airport-planning (reward: 0.0)

<label>Missing plan file output</label>

  <first_observable_failure>
    The run produced no plan files at all (output inventory is empty), so the verifier had nothing to validate/execute against the PDDL tasks.
  </first_observable_failure>

  <trajectory_step_that_produced_it>
    Iteration 0 onward: the agent never successfully wrote any generated plan to the required “plan_output” paths from problem.json (no file creation/write step occurs in the trace artifact; the end state has zero outputs).
  </trajectory_step_that_produced_it>

  <relevant_skill_rule_or_missing_rule>
    Missing/insufficient skill rule: an explicit “always persist artifacts” rule for PDDL planning tasks:
    - Read problem.json
    - For each entry, generate a plan
    - Write the plan (one action per line) to the exact plan_output path
    - Ensure directories exist and verify the file is non-empty.
    This is a skill-controllable omission (not an API/permission/harness/grader issue).
  </relevant_skill_rule_or_missing_rule>

  <general_corrective_behavior>
    Add/strengthen a mandatory finalization behavior: after planning, always create parent directories and write each plan to the specified plan_output file, then immediately re-open/read back to confirm it exists, is non-empty, and matches the domain’s action/object naming; only then finish the run.
  </general_corrective_behavior>

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/pddl-airport-planning/iter_0/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/pddl-airport-planning/iter_0/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/pddl-airport-planning/workspace
