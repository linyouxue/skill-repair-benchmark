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
problem = load_problem("domain.pddl", "task01.pddl")
```

**Notes**:

- Uses unified_planning.io.PDDLReader.
- Raises an error if parsing fails.

## 2. Plan Generation
### `generate-plan(problem_object)`

**Description**:
Generates a plan for the given planning problem using a classical planner.

**Parameters**:

- `problem_object`: A unified planning problem instance.

**Returns**:

- `plan_object`: A sequential plan.

**Example**:

```python
plan = generate_plan(problem)
```

**Notes**:

- Uses `unified_planning.shortcuts.OneshotPlanner`.
- Default planner: `pyperplan`.
- If no plan exists, returns None.

## 3. Plan Saving
### `save-plan(plan_output_path, plan_lines, overwrite=True)`

**Description**:
Writes a pre-formatted plan to disk at the exact literal path requested by the caller. This function does NOT use `unified_planning.io.PDDLWriter` for the final output, because the task prompt requires a specific per-line textual format (`action-name(arg1, arg2, ...)`) and a specific destination path taken verbatim from `problem.json`'s `plan_output` field.

**Inputs (contract)**:
- `plan_output_path` (str, required): Literal destination path copied verbatim from the task's `plan_output` field in `problem.json`. Must not be renamed, moved, suffixed, or extension-changed. Treat it as the authoritative output location.
- `plan_lines` (list[str], required, non-empty): Ordered action strings already formatted as `action-name(arg1, arg2, ...)`. Each entry must be stripped of trailing whitespace, contain no embedded newlines, no code fences, no comments, no numbering.
- `overwrite` (bool, default `True`): Overwrite existing file if present.

**Returns**:
- `dict` with `absolute_path` (str, resolved absolute path actually written) and `line_count` (int, number of action lines written).

**Required behaviour**:
1. Resolve the parent directory of `plan_output_path` and create it (and any missing ancestors) — equivalent to `mkdir -p`.
2. If the file exists and `overwrite` is False, raise an error; otherwise overwrite.
3. Open the file in text mode with UTF-8 encoding, no BOM, newline `\n`.
4. Write `"\n".join(plan_lines) + "\n"` — one action per line, single trailing newline, no blank lines, no wrapping code fences, no prose.
5. After writing, re-read the file (round-trip verification) and assert:
   - File is non-empty.
   - Line count (excluding the trailing empty line) equals `len(plan_lines)`.
   - Each non-empty line matches the pattern `name(arg, arg, ...)` or `name()`.
   - Content is byte-identical to what was intended to be written.
6. Return `{"absolute_path": ..., "line_count": ...}`.

**Example**:
```python
result = save_plan(
    plan_output_path=task["plan_output"],  # literal, from problem.json
    plan_lines=[
        "move(airplane1, seg_a, seg_b, north, south)",
        "takeoff(airplane1, runway1)",
    ],
    overwrite=True,
)
assert result["line_count"] == 2
```

**Notes**:
- Do NOT substitute `unified_planning.io.PDDLWriter` here; its output format and chosen path do not match the task contract.
- The literal `plan_output` path from `problem.json` is authoritative; never alter it.
- If the planner returns a `unified_planning` plan object, convert each action to the required `name(arg1, arg2, ...)` string before calling `save-plan`.

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

- Uses `unified_planning.shortcuts.SequentialPlanValidator`.
- Ensures goal satisfaction and action correctness.

# Example Workflow
```python
import json

with open("problem.json", "r", encoding="utf-8") as f:
    tasks = json.load(f)

for task in tasks:
    # 1. Load domain + problem
    problem = load_problem(task["domain"], task["problem"])

    # 2. Generate plan
    plan = generate_plan(problem)
    if plan is None:
        raise ValueError(f"No plan found for {task['id']}")

    # 3. Validate plan (semantic correctness)
    if not validate(problem, plan):
        raise ValueError(f"Generated plan is invalid for {task['id']}")

    # 4. Convert plan to required textual format: action-name(arg1, arg2, ...)
    plan_lines = []
    for action in plan.actions:  # unified_planning sequential plan actions
        name = action.action.name
        args = ", ".join(str(p) for p in action.actual_parameters)
        plan_lines.append(f"{name}({args})")
    assert plan_lines, "empty plan is not acceptable"

    # 5. Save to the EXACT path from problem.json (no renaming, no extension changes)
    result = save_plan(
        plan_output_path=task["plan_output"],
        plan_lines=plan_lines,
        overwrite=True,
    )

    # 6. Round-trip verification
    with open(task["plan_output"], "r", encoding="utf-8") as fh:
        written = [ln for ln in fh.read().split("\n") if ln.strip()]
    assert written == plan_lines, f"round-trip mismatch for {task['id']}"
    assert result["line_count"] == len(plan_lines)
```

# Notes

- This skill set enables reproducible planning pipelines.
- Designed for PDDL benchmarks and automated plan synthesis tasks.
- Ensures oracle solutions are fully verifiable.
- The `plan_output` path in `problem.json` is always authoritative and used verbatim; parent directories are created as needed; outputs are round-trip verified before advancing to the next task.
