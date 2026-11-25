---
name: skilltta-task-guidance
---

# Skill: PDDL Airport Planning — workflow + correct plan saving

This skill provides **reusable task guidance** for IPC-style PDDL airport-ground-traffic problems: how to load inputs, produce a plan, and **save the plan in the exact required format/path**.

## 1) Expected task I/O (what to read)

You will be given a `problem.json` that is a **list of task entries** like:

```json
[
  {
    "id": "problem_id",
    "domain": ".../domain.pddl",
    "problem": ".../problem.pddl",
    "plan_output": ".../problem_id.txt"
  }
]
```

For each entry:

- Read the **domain PDDL** from `entry["domain"]`
- Read the **problem PDDL** from `entry["problem"]`
- Write the resulting plan to the exact file path `entry["plan_output"]`

Paths may be relative; treat them as filesystem paths.

## 2) Plan format requirements (what to write)

A valid plan file must satisfy:

- **One grounded action per line**
- **No extra JSON, numbering, timestamps, commentary, or brackets**
- Action/object names must match exactly those in the domain/problem
- The plan should be directly parseable as a sequence of action applications

Example (each on its own line):

```
drive(truck1, depot1, market1)
load(goods1, truck1, market1, level0, level1, level0, level1)
...
```

If your planner returns actions in another textual style (e.g., `(drive truck1 depot1 market1)`), convert only if necessary to match the task’s expected syntax. If the benchmark expects the “`name(arg, ...)`” style, keep it consistent across all lines.

## 3) Example workflow (high level)

For each task:

1. **Load files**: read domain/problem PDDL text.
2. **Generate plan**:
   - Prefer calling an available planner component/library.
   - Ensure the plan is a sequence of **ground** actions using objects from the problem.
3. **Save plan** using the dedicated plan-saving routine (see next section).

## 4) Plan saving (common failure points + robust routine)

### Common mistakes

- Writing the plan as a Python list representation (e.g., `['a', 'b']`) instead of line-separated text
- Forgetting to create parent directories for `plan_output`
- Adding numbering like `0: action(...)` when the evaluator expects raw action lines
- Trailing spaces / blank lines that some checkers treat as extra actions

### Required behavior

- Create parent directories for `plan_output` if they do not exist
- Write exactly one action per line
- End file with a newline (safe default)

### Canonical save routine

Pseudocode:

```python
import os

def save_plan(plan_output: str, plan):
    # plan can be a string (multi-line) or a list of action strings
    os.makedirs(os.path.dirname(plan_output) or '.', exist_ok=True)

    if isinstance(plan, str):
        # normalize line endings and strip extra blank lines
        lines = [ln.strip() for ln in plan.splitlines() if ln.strip()]
    else:
        lines = [str(a).strip() for a in plan if str(a).strip()]

    with open(plan_output, 'w', encoding='utf-8') as f:
        for act in lines:
            f.write(act + '\n')

    return plan_output
```

## 5) `save_plan.skill` interface (inputs definition)

If your system uses a separate `save_plan.skill`, define its inputs so it can be called consistently from planners.

**Recommended inputs** (minimal and unambiguous):

- `plan_output` (string): output file path from `problem.json`
- `plan` (string OR list[string]): the plan content (already grounded actions)

Notes:

- Do **not** require the caller to pass `id`, `domain`, or `problem` into `save_plan`.
- Accepting both `str` and `list[str]` avoids brittle coupling to any single planner’s return type.

## 6) Lightweight validation before saving (optional but useful)

Before writing, validate:

- `len(lines) > 0` (unless you are certain the problem is already at goal)
- No line contains forbidden prefixes like `";"`, `"#"`, or step numbers like `"0:"`
- Each line contains an action name and parentheses (if using `name(arg,...)` style)

This doesn’t prove correctness, but catches frequent formatting errors.
