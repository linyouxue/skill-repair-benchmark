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

---

# PDDL Skills

## Naming convention (important)

All public-facing skill names in this bundle use **snake_case**:

- `load_problem(...)`
- `generate_plan(...)`
- `save_plan(...)`
- `validate(...)`

Do **not** mix hyphenated names (e.g., `load-problem`) with snake_case in callers/examples.

## 1. Load Domain and Problem

### `load_problem(domain_path, problem_path)`

**Description**:  
Loads a PDDL domain file and problem file into a Unified Planning problem object.

**Parameters**:
- `domain_path` (str): Path to PDDL domain file.
- `problem_path` (str): Path to PDDL problem file.

**Returns**:
- `problem_object`: A `unified_planning.model.Problem` instance.

**Example**:
```python
problem = load_problem("domain.pddl", "task01.pddl")
```

**Notes**:
- Typically implemented with `unified_planning.io.PDDLReader`.
- Raise an error if parsing fails.

## 2. Plan Generation

### `generate_plan(problem_object)`

**Description**:
Generates a plan for the given planning problem using an available classical planner.

**Parameters**:
- `problem_object`: A Unified Planning problem instance.

**Returns**:
- `plan_object`: A sequential plan (or a list of grounded action strings), depending on implementation.

**Example**:
```python
plan = generate_plan(problem)
```

**Notes**:
- Commonly implemented via `unified_planning.shortcuts.OneshotPlanner`.
- Planner availability depends on the runtime (e.g., `pyperplan` may or may not be installed).
- If no plan exists, return `None`.

## 3. Plan Saving

### `save_plan(plan_output, plan)`

**Description**:
Writes a plan to disk in the **benchmark-required plain text format**:

- **one grounded action per line**
- **no** step numbers, timestamps, comments, JSON, brackets, or extra annotations
- write to the **exact** `plan_output` path
- create parent directories if needed

**Parameters**:
- `plan_output` (str): Output file path (typically `entry["plan_output"]` from `problem.json`).
- `plan`: Either:
  - a multi-line string containing one action per line, or
  - a list/iterable of action strings, or
  - a planner-specific plan object that your code can stringify into grounded actions.

**Example**:
```python
save_plan("solutions/task01.txt", plan)
```

**Implementation guidance (robust, format-safe)**:

Do **not** rely on a generic PDDL domain/problem writer (e.g., `PDDLWriter`) for plan serialization, because benchmark plan checkers usually expect a very specific “one action per line” text format.

Pseudocode:
```python
import os

def save_plan(plan_output: str, plan):
    os.makedirs(os.path.dirname(plan_output) or '.', exist_ok=True)

    # Accept either a multi-line string or an iterable of actions.
    if isinstance(plan, str):
        lines = [ln.strip() for ln in plan.splitlines() if ln.strip()]
    else:
        lines = [str(a).strip() for a in plan if str(a).strip()]

    # Write exactly one action per line.
    with open(plan_output, 'w', encoding='utf-8') as f:
        for act in lines:
            f.write(act + "\n")

    return plan_output
```

### `save_plan.skill` interface (inputs definition)

If your framework uses a separate executable `save_plan.skill`, its inputs should be minimal and stable:

- `plan_output` (string): output file path from `problem.json`
- `plan` (string OR list[string]): plan content

Do **not** require unrelated inputs (like `id/domain/problem`) for plan saving.

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
ok = validate(problem, plan)
```

**Notes**:
- Validator APIs vary across Unified Planning versions/installed engines.
- Treat validation as optional if a compatible validator engine is not available.
- If you do validate, ensure it checks applicability and goal satisfaction.

# Example Workflow (aligned with problem.json + plan_output)

```python
import json

with open("problem.json", "r", encoding="utf-8") as f:
    entries = json.load(f)

for entry in entries:
    # Load
    problem = load_problem(entry["domain"], entry["problem"])

    # Generate
    plan = generate_plan(problem)
    if plan is None:
        raise RuntimeError(f"No plan found for task {entry.get('id')}")

    # Validate (optional)
    # if not validate(problem, plan):
    #     raise ValueError("Generated plan is invalid")

    # Save to the required output path
    save_plan(entry["plan_output"], plan)
```

# Notes

- This skill set enables reproducible planning pipelines for IPC-style PDDL benchmarks.
- Plan files must be saved in strict line-per-action format to the exact `plan_output` path.
