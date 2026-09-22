---
name: pddl-skills
description: "Automated Planning utilities for loading PDDL domains and problems, generating plans using classical planners, validating plans, and saving plan outputs. Supports standard PDDL parsing, plan synthesis, and correctness verification."
license: Proprietary. LICENSE.txt has complete terms
---

# Requirements for Outputs

## General Guidelines

### PDDL Files
- Domain files must follow PDDL standard syntax.
- Problem files must reference the correct domain.
- Plans must be sequential classical plans.

### Planner Behavior
- Planning must terminate within timeout.
- If no plan exists, return an empty plan or explicit failure flag.
- Validation must confirm goal satisfaction.

### Plan File Output Format (CRITICAL)
Written plan files MUST use **standard PDDL S-expression syntax**, because downstream
verifiers typically re-parse them with `unified_planning.io.PDDLReader.parse_plan`,
which only accepts lines matching:

- Sequential: `(action-name arg1 arg2 ... argN)`  — one action per line
- Time-triggered: `start-time: (action-name arg1 ... argN) [duration]`
- Blank lines and `; comments` are allowed.

Do **not** use Python-style `action(arg1, arg2)` with commas between arguments,
even if a task's natural-language prompt shows an example in that form. The example in
the task description (e.g., `drive(truck1, depot1, market1)`) is illustrative of
ordering and naming only — it is **not** the required serialization. Arguments must be
space-separated and the entire action must be wrapped in a single pair of parentheses.

Correct:
```
(move_seg_rw_0_400_seg_rww_0_50_south_south_medium airplane_cfbeg)
(park_seg_pp_0_60_south airplane_cfbeg)
```

Incorrect (will fail PDDLReader.parse_plan):
```
move_seg_rw_0_400_seg_rww_0_50_south_south_medium(airplane_cfbeg)
park_seg_pp_0_60_south(airplane_cfbeg)
```

Action names and object names must exactly match those in the domain/problem
(case is normalized to lowercase by the reader; emit lowercase to be safe).

---

# PDDL Skills

## 1. Load Domain and Problem

### `load-problem(domain_path, problem_path)`

**Description**:  
Loads a PDDL domain file and problem file into a unified planning problem object.

**Parameters**:
- `domain_path` (str): Path to PDDL domain file.
- `problem_path` (str): Path to PDDL problem file.

**Returns**:
- `problem_object`: A `unified_planning.model.Problem` instance.

**Example**:
```python
from unified_planning.io import PDDLReader
reader = PDDLReader()
problem = reader.parse_problem("domain.pddl", "task01.pddl")
```

**Notes**:
- Uses `unified_planning.io.PDDLReader`.
- Raises an error if parsing fails.

## 2. Plan Generation
### `generate-plan(problem_object)`

**Description**:
Generates a plan for the given planning problem using a classical planner.

**Parameters**:
- `problem_object`: A unified planning problem instance.

**Returns**:
- `plan_object`: A sequential plan (or `None` if unsolvable).

**Example**:
```python
from unified_planning.shortcuts import OneshotPlanner
with OneshotPlanner(name="pyperplan") as planner:
    result = planner.solve(problem)
plan = result.plan
```

**Notes**:
- Uses `unified_planning.shortcuts.OneshotPlanner`.
- Default planner: `pyperplan`.
- If no plan exists, returns `None`.

## 3. Plan Saving
### `save-plan(plan_object, output_path)`

**Description**:
Writes a plan object to disk in **standard PDDL plan format** (S-expressions), one
action per line, so that `PDDLReader.parse_plan` (used by many verifiers) can read
it back.

**Required line format** (sequential plans):
```
(<action-name> <arg1> <arg2> ... <argN>)
```

**Recommended implementation** — do NOT hand-format with Python `f"{name}({a}, {b})"`.
Either:

A. Use unified_planning's own writer helpers, e.g. iterate `plan.actions` and emit
   PDDL syntax explicitly:
```python
def save_plan(plan, output_path):
    lines = []
    for ai in plan.actions:
        name = ai.action.name
        args = " ".join(str(p) for p in ai.actual_parameters)
        lines.append(f"({name} {args})" if args else f"({name})")
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
```

B. Or reuse the string form of `ActionInstance` (which already renders as
   `action_name(a, b)` in unified_planning) **only after converting** commas to
   spaces and rewrapping — but option A is simpler and less error-prone.

**Verification after writing (REQUIRED)**:
Immediately re-parse the written file with `PDDLReader.parse_plan(problem, path)`
to confirm the on-disk format is accepted. This mirrors what the verifier does
and catches formatting mistakes before finishing the task.

```python
from unified_planning.io import PDDLReader
reader = PDDLReader()
parsed = reader.parse_plan(problem, output_path)  # raises UPException on bad format
```

## 4. Plan Validation
### `validate(problem_object, plan_object)`

**Description**:
Validates that a plan correctly solves the given PDDL problem.

**Parameters**:
- `problem_object`: The planning problem.
- `plan_object`: The generated plan.

**Returns**:
- bool: True if the plan is valid, False otherwise.

**Example**:
```python
from unified_planning.shortcuts import PlanValidator
with PlanValidator(problem_kind=problem.kind, plan_kind=plan.kind) as v:
    ok = v.validate(problem, plan).status.name == "VALID"
```

**Notes**:
- Validates the in-memory plan object. This does NOT check the on-disk
  serialization — always additionally re-parse the written file (see §3).

# Example Workflow
```python
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner, PlanValidator, get_environment
get_environment().credits_stream = None

reader = PDDLReader()
problem = reader.parse_problem("domain.pddl", "task01.pddl")

with OneshotPlanner(name="pyperplan") as planner:
    plan = planner.solve(problem).plan
assert plan is not None, "No plan found"

# Validate in-memory plan
with PlanValidator(problem_kind=problem.kind, plan_kind=plan.kind) as v:
    assert v.validate(problem, plan).status.name == "VALID"

# Save in standard PDDL S-expression format
out = "task01.txt"
with open(out, "w") as f:
    for ai in plan.actions:
        args = " ".join(str(p) for p in ai.actual_parameters)
        f.write(f"({ai.action.name} {args})\n" if args else f"({ai.action.name})\n")

# Sanity check: verifier will re-parse the same way
reader.parse_plan(problem, out)
```

# Common Pitfalls

- **Wrong output syntax**: Emitting `action(a, b)` instead of `(action a b)` causes
  `UPException: Cannot interpret ...` during verifier re-parsing. Always use the
  S-expression form.
- **Comma separators**: PDDL uses whitespace between arguments, never commas.
- **Missing outer parentheses**: Every action line must be wrapped in `(...)`.
- **Trusting task-prompt examples verbatim**: Natural-language task prompts may show
  actions as `name(a, b)` for readability. Treat these as pseudocode; the on-disk
  format must be PDDL S-expressions.
- **Skipping post-write re-parse**: In-memory `PlanValidator` success does not imply
  the file is well-formed. Always call `PDDLReader.parse_plan` on the written file.

# Notes

- This skill set enables reproducible planning pipelines.
- Designed for PDDL benchmarks (IPC domains such as airport, depots, etc.) and
  automated plan synthesis tasks.
- Ensures oracle solutions are fully verifiable end-to-end (planner → file → re-parse).
