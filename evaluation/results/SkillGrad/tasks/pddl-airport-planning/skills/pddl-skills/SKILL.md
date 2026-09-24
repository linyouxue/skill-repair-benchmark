---
name: pddl-skills
description: "Load PDDL problems, generate and validate classical plans, and persist one plan artifact per required output path from the task’s problem.json inventory."
license: Proprietary. LICENSE.txt has complete terms
---

## Plan-first workflow (do this before coding)

1. Read `problem.json` (or equivalent task manifest) and enumerate every required `plan_output` path.
2. For each item, record: `(domain_path, problem_path, plan_output)` and treat this inventory as the definition of “done”.
3. Choose the planner stack (e.g., Unified Planning + oneshot planner) and the failure convention (empty plan vs explicit marker) *before* running.

## Finalize: persist required plan artifacts

1. Name the completion gate (e.g., `PERSIST_ALL_OUTPUTS`) and run it exactly once as your last tool-assisted action.
2. The gate must: re-open `problem.json`, re-enumerate every required `plan_output`, write exactly one file per path, then read back each file.
3. Immediately before `end_turn`, state a one-line assertion in your final message: `All plan_output files listed in problem.json exist on disk.`

Read references/persist_plan_outputs.md when `problem.json` contains one or more `plan_output` file paths.
Skip when the harness collects plans from stdout instead of files.

# PDDL Skills

## Load Domain and Problem

Load a domain/problem pair into a planning problem object.

```python
from unified_planning.io import PDDLReader

reader = PDDLReader()
problem = reader.parse_problem(domain_path, problem_path)
```

## Plan Generation

Generate a sequential plan using a classical planner; treat “no plan found” as a first-class outcome.

```python
from unified_planning.shortcuts import OneshotPlanner

with OneshotPlanner() as planner:
    result = planner.solve(problem)
plan = result.plan  # may be None
```

## Plan Validation

Validate that the plan solves the problem before persisting it.

```python
from unified_planning.shortcuts import SequentialPlanValidator

validator = SequentialPlanValidator(problem.kind)
ok = (plan is not None) and validator.validate(problem, plan)
```

## Plan Saving

Persist plans to the required output path(s); ensure directories exist.

```python
from pathlib import Path

Path(output_path).parent.mkdir(parents=True, exist_ok=True)
Path(output_path).write_text(plan_text, encoding="utf-8")
```

**Decision rule:** If the benchmark specifies `plan_output` file paths, treat missing/empty outputs as a higher-priority failure than suboptimal plan length.

## Common Pitfalls

- Finishing without writing the required plan artifacts (always enumerate `plan_output` paths and persist one file per item).
- Writing to the wrong location or wrong filename (use the exact paths from the task manifest).
- Skipping read-back verification (a plan “saved” to a non-existent directory is equivalent to no output).
- Treating “no plan” as “no output” (still write an explicit artifact matching the harness convention).
