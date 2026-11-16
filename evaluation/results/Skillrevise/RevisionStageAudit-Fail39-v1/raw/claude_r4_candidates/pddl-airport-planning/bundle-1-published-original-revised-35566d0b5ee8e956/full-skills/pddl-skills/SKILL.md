# PDDL Planning Pipeline

## Purpose
Produce verifiable classical plans for PDDL task batches by loading domain/problem files, synthesizing a sequential plan, writing it in the exact action-line grammar required by the task's external verifier, and reloading the file to confirm format compliance.

## When to Use
Use when a repository provides one or more PDDL domain/problem pairs together with a driver manifest (commonly `problem.json` or equivalent) that declares, per task, input paths and an output plan path, and the acceptance test reads a plain-text plan file whose lines must match a specific action syntax.

## Procedure
- Discover the task manifest: locate the driver file (e.g., `problem.json`) at the repository root or working directory; parse it to obtain a list of tasks, each with `domain`, `problem`, and `plan_output` (or equivalently named) fields. If no manifest exists, fall back to explicit CLI args; never hardcode filenames.
- Validate inputs: for each task, assert the domain and problem files exist and are readable, and that the parent directory of `plan_output` is writable. Parse with `unified_planning.io.PDDLReader`; on parse error, record the failure for that task and continue.
- Plan with discovery and fallback: call `OneshotPlanner(problem_kind=problem.kind)` to let UP select a compatible engine; if that fails or times out, retry with explicit `name="pyperplan"`, then `name="fast-downward"` if available. Apply a per-task timeout (e.g., `OneshotPlanner(... , timeout=...)`). If no plan is returned, write an empty file or declared failure sentinel per task contract and move on.
- Internal sanity check then serialize: run `SequentialPlanValidator` on the UP plan; only if valid, serialize each action as `f"{act.action.name}({', '.join(str(p) for p in act.actual_parameters)})"` (lowercase identifiers matching the PDDL source), join with `\n`, and write to the task's declared `plan_output` path.
- Post-write verification: reopen the written file; for every non-empty line, assert it matches the regex `^[A-Za-z0-9_\-]+\([^()]*\)$` and that referenced action and object names appear in the parsed domain/problem symbol tables. If any line fails, raise and do not mark the task complete.

## Constraints / Pitfalls
- Do not use `str(action)` from unified_planning as the serialization source; its default form may be LISP-style `(name a b)` or include types and will not match a `name(a, b)` grammar.
- Do not treat `SequentialPlanValidator=VALID` as task acceptance; it only confirms internal semantic validity, not external file grammar or path correctness.
- Do not hardcode planner names, file paths, or a single task; drive everything from the discovered manifest and from available engines reported by `unified_planning.shortcuts`.
- Preserve exact case and underscores from the PDDL source when emitting action and parameter names; do not inject types, quotes, or extra whitespace inside the parentheses beyond `, ` separators.
- Always write to the task-declared output path; if writing fails, inspect permissions and manifest fields rather than silently redirecting to an alternate path.