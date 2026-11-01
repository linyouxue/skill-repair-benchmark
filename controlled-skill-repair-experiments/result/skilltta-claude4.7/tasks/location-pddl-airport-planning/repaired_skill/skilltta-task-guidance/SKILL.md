---
name: skilltta-task-guidance
description: Temporary task-guidance for PDDL airport ground-traffic planning tasks, focused on correct plan generation and robust saving of the plan to the exact path specified in problem.json.
---

# PDDL Airport Planning – Task Guidance

## Scope
Solve airport ground-traffic PDDL tasks from IPC suites. For each entry in `problem.json`:
1. Read `domain` and `problem` file paths.
2. Produce a valid PDDL plan.
3. Write the plan to the **exact** path given by `plan_output` (verbatim, no renaming, no extension changes).

## Key failure mode to avoid (per location hint)
The prior skill’s `Plan Saving` section, `Example Workflow`, and `save_plan.skill` input definition mishandle plan output. Fix the following before saving:

### Plan Saving (corrected)
- Treat `plan_output` as the authoritative, literal destination path. Do **not** prepend or rewrite directories, do **not** change the file name, do **not** append suffixes like `.plan` or `.pddl`.
- Ensure the parent directory exists (`mkdir -p` equivalent) before writing. Missing directories are the most common silent failure.
- Write using UTF-8, newline `\n`, no BOM. One action per line. No trailing commentary, no code fences, no leading blank lines.
- Do **not** wrap actions in `(` `)` unless the planner output already uses that form; the example format in the task prompt is `action(arg1, arg2, ...)` per line — match whatever grounded action signature the domain expects.
- After writing, re-read the file and verify: non-empty, every non-empty line parses as `name(arg, arg, ...)`, and action/object names appear in the domain/problem.

### save_plan.skill inputs (corrected contract)
Required inputs:
- `plan_output_path` (string, required): literal path from `problem.json`’s `plan_output`. Must be used as-is.
- `plan_lines` (list[str], required): ordered action strings, already stripped of trailing whitespace, no empty entries.
- `overwrite` (bool, default true): overwrite if the file exists.
Behaviour:
- Create parent directories.
- Join `plan_lines` with `\n` and append a final newline.
- Return the resolved absolute path actually written, plus line count, for post-write assertion.

### Example Workflow (corrected)
```
for task in problem.json:
    domain_text  = read(task.domain)
    problem_text = read(task.problem)
    plan_lines   = plan(domain_text, problem_text)   # list[str]
    assert plan_lines, "empty plan is invalid"
    save_plan(plan_output_path=task.plan_output,
              plan_lines=plan_lines,
              overwrite=True)
    verify_written(task.plan_output, plan_lines)
```

## Planning guidance for airport domain
- Objects typically include airplanes, segments, directions, runways. Preconditions involve `blocked`, `occupied`, `facing`, `at-segment`, `is-moving`/`is-pushing` style predicates (names vary by domain variant: `airport`, `airport-adl`, `airport-strips`).
- Core action schemas usually are: `move`, `move-back`, `pushback`, `startup`, `park`, `takeoff`, `land`. Emit actions grounded with the exact object symbols from the problem file (case-sensitive).
- Respect segment adjacency and direction facing: insert `pushback` / direction changes before attempting a `move` that violates `facing`.
- Keep plans short: prefer shortest path through the taxi graph; avoid revisiting segments unless required to clear a blocked region.
- For large (Munich-scale) instances, if full optimal search is infeasible, produce a sound sequential plan that satisfies the goal; validity matters, optimality does not.

## Output format rules (strict)
- One action per line, formatted as `action-name(obj1, obj2, ...)` matching the prompt’s example style.
- No numbering, no timestamps, no comments, no blank lines between actions.
- File ends with a single trailing newline.

## Transferable pattern from retrieved examples
The retrieved examples (pickle save/load, DataFrame augmentation) share one discipline: **write to the exact declared filename, then read back and validate**. Apply the same round-trip check here — after writing the plan, reload it and confirm line count and format before moving to the next task.

## Pre-submit checklist
- [ ] File exists at the literal `plan_output` path.
- [ ] Parent directories created if missing.
- [ ] Every line matches `name(args)` and uses only symbols from domain/problem.
- [ ] No code fences, no prose, no empty plan.
- [ ] Round-trip read confirms identical content.
