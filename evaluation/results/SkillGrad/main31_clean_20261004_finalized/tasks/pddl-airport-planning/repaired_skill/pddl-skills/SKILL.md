---
name: pddl-skills
description: "Load PDDL problems, generate and validate plans, and write evaluator-compatible plan text files for benchmark submission."
license: Proprietary. LICENSE.txt has complete terms
---

## Quick Start (workflow)

1. Parse domain/problem and confirm object/action names match what you will emit.
2. Solve to a sequential plan; if unsolvable, emit an explicit failure artifact (empty plan file or flag).
3. Validate the plan against the problem.
4. Serialize the plan in the evaluator’s required *plan text syntax* (not library pretty-print).
5. Re-open the written plan file and sanity-check its syntax before returning.

## Load Domain and Problem

Use a PDDL reader to load both files into a single planning problem object.

```python
from unified_planning.io import PDDLReader

reader = PDDLReader()
problem = reader.parse_problem(domain_path, problem_path)
```

## Generate a Plan

Generate a sequential plan with a oneshot planner; treat `None` / unsolved status as “no plan”.

```python
from unified_planning.shortcuts import OneshotPlanner

with OneshotPlanner(name=planner_name) as planner:
    result = planner.solve(problem)
plan = getattr(result, "plan", None)
```

## Validate a Plan

Validate action applicability and goal satisfaction on the produced plan.

```python
from unified_planning.shortcuts import PlanValidator

validator = PlanValidator(name="sequential_plan_validator")
ok = validator.validate(problem, plan)
```

Decision rule: if validation fails, do not serialize; re-plan with a different planner/config or inspect unsupported features.

## Save a Plan (plan text serialization)

Write one action per line using *PDDL plan tokens* (typically parenthesized, whitespace-separated tokens): `(<action> <arg1> <arg2> ...)`.
Never write `str(action_instance)` to disk; many evaluators reject the library pretty-print form (often `name(arg)`-style).

```python
def serialize_action_instance(action_instance):
    name = action_instance.action.name
    args = [p.object().name for p in action_instance.actual_parameters]
    return "(" + " ".join([name] + args) + ")"

with open(output_path, "w", encoding="utf-8") as f:
    for ai in plan.actions:
        f.write(serialize_action_instance(ai) + "\n")
```

Read references/plan_text_serialization.md when the evaluator expects IPC-style plan text files or you see `name(arg)` / commas in your output.
Skip when you are using a dedicated writer that is known to emit the benchmark’s expected plan-file syntax.

## Common Pitfalls

- Confusing “validated in the planner library” with “accepted by the benchmark evaluator”: always verify the on-disk plan text syntax.
- Writing `str(ActionInstance)` (pretty-print) instead of PDDL plan tokens: enforce `(<name> <arg1> ...)` and re-open the file to sanity-check.
