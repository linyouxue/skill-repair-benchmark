---
name: pddl-skills
description: "Automated Planning utilities for loading PDDL domains and problems, generating plans with classical planners, validating plans, and saving plans in grader-compatible plan-file format."
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

### Plan Output Files
- One action per line. The surface shape of each line is a combination of
  **three independent decisions** — surface wrapper, schema expansion, and
  case convention — each resolved from its own evidence (see workflow
  section below). The planning library's default emitter is never
  authoritative on its own.
- Canonical IPC form `(action arg1 arg2 ...)` — parens, space-separated,
  lowercase, no cost annotations — is a per-sub-track fallback, not a
  global default. One sub-track may follow the task spec while another
  falls back to canonical.
- A semantically valid plan (`SequentialPlanValidator` VALID) is not
  automatically a grader-accepted plan: the validator checks the plan
  object; the grader reads the file text. The written file must match
  the grader's expected shape.

---

# Locate the format authority before planning

Before writing code, resolve **three independent sub-tracks**. Each has
its own ranked candidate list; pick the highest-ranked candidate that is
actually present. Record what you picked for each sub-track and the
first-line fingerprint. Serializers downstream (`save-plan`,
`verify-plan`) read these decisions; do not revisit them ad hoc after
`validate` returns True.

**Sub-track 1 — Surface wrapper** (`(verb args...)` vs `verb(args, ...)`):
1. worked plan line in task description/prompt;
2. reference plan file in task bundle (`*.plan`, `*.soln`, `plan.txt`);
3. prose spec on surface syntax;
4. canonical IPC default `(verb args...)`.

**Sub-track 2 — Schema expansion** (full pre-grounded schema as one head
token vs split verb + baked-in constants):
1. **domain inspection on the CURRENT task's domain.** If any `:action`
   identifier embeds object constants as underscore-joined tokens (e.g.
   `move_<seg>_<seg>_<dir>_<dir>_<type>`, or more generally any `:action`
   whose `:parameters` list is shorter than the underscore-joined parts
   of its own name), the domain is **pre-grounded** and
   `head_is_schema = True`. This rank-1 signal **overrides** any example
   whose head happens to look like a plain verb, because the example's
   domain family (e.g. depot/truck `drive(truck1, depot1, market1)`) is
   not pre-grounded and therefore its head shape is **absent evidence**
   about schema expansion in the current domain — not negative evidence.
2. task example head-token shape, **only when the example's domain family
   matches the current task's domain family** (both plain-verb or both
   pre-grounded).
3. reference plan head-token shape (same cross-family caveat).
4. canonical fallback — split if pre-grounded, else identity.

**Sub-track 3 — Case convention** (uppercase/lowercase of head and args):
1. task example case pattern;
2. **raw PDDL problem/domain file identifier case, whenever the task
   description states that plan tokens must match the PDDL files or
   otherwise asserts case sensitivity against them.** Read `(:objects
   ...)` and `(:init ...)` from the raw problem text and build a
   `case_map: {lowercase_token: original_case_token}`; apply the map
   to every emitted head and arg;
3. planner's `str(p)` lowercase verbatim.

Decision rule: the three sub-tracks are **orthogonal** — resolve each
from its own evidence. **Evidence from one sub-track never drives a
decision in another.** A plain-verb example tells you wrapper, separator,
and case; it does not tell you to split a pre-grounded schema. If the
current task's domain is pre-grounded, `head_is_schema = True` regardless
of what any example's head looks like.

Read `references/plan-output-format.md` when the domain is pre-grounded,
OR the task provides a plan-line example, OR the task prose asserts
case sensitivity against the PDDL files. Skip when action names are
plain verbs AND no task example is provided AND the task prose does
not tie plan tokens to PDDL file identifiers.

---

# PDDL Skills

## 1. Load Domain and Problem

### `load-problem(domain_path, problem_path)`

Loads a PDDL domain file and problem file into a unified planning problem.

```python
from unified_planning.io import PDDLReader
problem = PDDLReader().parse_problem("domain.pddl", "problem.pddl")
```

Notes: raises on parse failure. Keep the raw domain **and problem** file
paths around; the save step may re-read them to detect pre-grounding and
to recover original-case object identifiers (PDDLReader lowercases all
tokens internally).

## 2. Plan Generation

### `generate-plan(problem_object)`

Generates a sequential plan via `OneshotPlanner` (default: `pyperplan`).

```python
from unified_planning.shortcuts import OneshotPlanner
with OneshotPlanner(name="pyperplan") as planner:
    result = planner.solve(problem)
plan = result.plan  # None if unsolvable
```

Decision rule: if `plan is None`, do not write an output file — report
failure explicitly. An empty-but-non-None plan is a legal zero-step solution
and must still be written.

## 3. Plan Saving

### `save-plan(plan_object, output_path, example_line=None, case_map=None, domain_path=None)`

Write one action per line. Three orthogonal decisions, each already
resolved by the planning-step workflow:

- **Surface wrapper** — set by example, else canonical IPC `(verb args...)`.
- **Schema expansion** — set by **domain inspection on `domain_path`**;
  pre-grounded domain forces the full `action.name` as the head token,
  regardless of what any example's head looks like.
- **Case convention** — set by `case_map` if non-empty, else `str(p)` verbatim.

```python
def save_plan(plan, output_path, example_line=None, case_map=None,
              domain_path=None):
    # example_line: first non-blank action line from task example (None →
    #   canonical wrapper + canonical schema expansion).
    # case_map: {lowercase_token: original_case_token} — populated from
    #   task example OR from problem-file objects when prose spec demands
    #   match. None/empty → planner lowercase verbatim.
    # domain_path: raw PDDL domain path — used to detect pre-grounding
    #   so the save loop never splits a pre-grounded schema even when
    #   example_line's head looks plain-verb.
    with open(output_path, "w") as f:
        for ai in plan.actions:
            line = format_action(ai, example_line, case_map, domain_path)
            f.write(line + "\n")                           # see references/
```

Decision rule — **schema expansion**: if `is_pregrounded_domain(domain_path)`
is True, `format_action` must emit `ai.action.name` as a **single** head
token and only `ai.actual_parameters` as args. Never run the head through
`recover_action` / `split_prefix` / any `:constants` longest-prefix match
in this case, even if `example_line` is `verb(args, ...)`-shaped. The
example controls wrapper, separator, and case — not schema expansion.

Decision rule — **case**: re-case tokens against the **highest-ranked
case authority present** — task example case pattern > problem/domain
file case (when task prose demands match-the-PDDL-files) > planner
lowercase. Never default to `str(p)` verbatim when the task prose
contains "match the PDDL domain", "match the PDDL problem",
"case-sensitive", or similar language promoting the raw files; in that
situation build a `case_map` from the problem/domain file and pass it in.

Read `references/plan-output-format.md` for the pre-grounding detector,
the schema-splitting algorithm (used only in the canonical-IPC fallback
when the domain is NOT pre-grounded, or when the example is itself from
a matching pre-grounded family), the example-mirroring algorithm, the
case-map construction procedure, and worked airport-family examples.
Skip when action identifiers are plain verbs AND no task example exists
AND the task prose does not tie plan tokens to the PDDL files.

## 4. Plan Validation

### `validate(problem_object, plan_object)`

```python
from unified_planning.shortcuts import SequentialPlanValidator
with SequentialPlanValidator() as v:
    ok = bool(v.validate(problem, plan))
```

Decision rule: `SequentialPlanValidator` VALID means the plan is
semantically correct against the domain model — it says **nothing** about
whether the written file's text matches the grader. Treat VALID as
necessary, not sufficient. Follow with the post-write check in the next
section.

---

# Verify the written plan file

After `save-plan`, re-open the output and compare its contents against
every format authority identified in the planning step. This is
**mandatory**, not optional — validator-pass is not a substitute.

Three checks, run in order:

- **Shape vs task example (if any) AND current domain.** Diff the first
  written line's fingerprint — outer wrapper, argument separator,
  head-token shape — against the example's first line. **Additionally**,
  if `domain_path` is pre-grounded, assert the emitted
  `head_is_schema == True` regardless of the example's head shape. Any
  mismatch means `save-plan` followed the wrong authority or let an
  example drive the schema sub-track.
- **Case vs case_map (if any).** For every token in every written line,
  if its lowercase form is a key in `case_map`, assert the token equals
  `case_map[lowercase]` character-for-character. Any mismatch means the
  case map was built but not applied, or applied inconsistently.
- **Canonical-IPC checks (no example / fallback).** Starts with `(`,
  ends with `)`, no commas inside, head is not a long underscored
  schema (indicates missed splitting on a non-pre-grounded domain).
  Case constraint drops when `case_map` is in effect; otherwise require
  lowercase inside.

```python
def verify_plan_file(path, example_line=None, case_map=None,
                    domain_path=None):
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith(";")]
    if not lines:
        return
    first = lines[0]
    if example_line is not None:
        # Shape fingerprint diff vs task example AND pre-grounding override.
        _assert_shape_matches(first, example_line, domain_path=domain_path)
    if case_map:
        _assert_case_matches(lines, case_map)
    if example_line is None:
        _assert_canonical_structure(lines, require_lowercase=(not case_map))
```

On failure of any check, the fix is in `save-plan` — never hand-edit the
output file. Read `references/plan-output-format.md` for branched
corrective actions keyed to each failure signature.

---

# Example Workflow

```python
# Step 1 (planning): resolve all three format sub-tracks.
example_line = find_task_example_line(task_dir)    # None if absent
case_map = {}
if example_line is not None:
    case_map = build_case_map_from_example(example_line, problem_path)
elif task_prose_demands_match_pddl_files(task_description):
    case_map = build_case_map_from_problem_file(problem_path, domain_path)

problem = load_problem("domain.pddl", "task01.pddl")
plan = generate_plan(problem)
if plan is None:
    raise RuntimeError("no plan found")
if not validate(problem, plan):
    raise ValueError("plan semantically invalid")

# domain_path is passed to BOTH save and verify so the pre-grounding
# override on schema expansion fires in both places. Validator-VALID is
# never a substitute for this post-write check.
save_plan(plan, "task01.plan",
          example_line=example_line, case_map=case_map,
          domain_path="domain.pddl")
verify_plan_file("task01.plan",
                 example_line=example_line, case_map=case_map,
                 domain_path="domain.pddl")
```

# Common Pitfalls

- **Validator-pass ≠ grader-pass.** `SequentialPlanValidator` only checks
  the semantic model; it ignores the on-disk text. Always run
  `verify_plan_file` with the same `example_line`, `case_map`, and
  `domain_path` used in `save-plan`.
- **Cross-contaminating evidence between sub-tracks (the recurring
  meta-defect).** The three sub-tracks are orthogonal: each decision
  must be driven by its own authority list. The two concrete faces of
  this defect: (a) committing to a single global format authority
  (library default, OR skill's canonical-IPC default, OR a prompt
  example, OR planner-lowercase passthrough) and ignoring the other
  sub-tracks; and (b) **letting evidence from the right sub-track drive
  a decision in a different sub-track** — most dangerously, letting a
  plain-verb task example (e.g. `drive(truck1, depot1, market1)` from a
  depot/truck family) drive schema splitting on a pre-grounded
  current-task domain. The example is evidence for wrapper, separator,
  and case only. For a pre-grounded current-task domain the correct
  airport output under a comma-call example is
  `move_seg_rw_0_400_seg_rww_0_50_south_south_medium(airplane_CFBEG)`;
  the wrong form is `move(airplane_CFBEG, seg_rw_0_400, ...)`. **Never
  invent a schema-splitting transform from scratch** (first-underscore
  verb, `:constants` longest-prefix match, etc.); schema splitting is
  only via `AIRPORT_VERBS` + `regroup_tokens` in the canonical-IPC
  fallback branch, and only when the current task's domain is actually
  pre-grounded.
- **Trusting `PDDLWriter.write_plan` on pre-grounded domains with no
  example.** It prints the whole underscored schema as one token.
  Without a task example, fall back to canonical IPC and split the
  schema — see `references/plan-output-format.md`.
- **Case convention set by the wrong authority — bidirectional.** PDDL
  is case-insensitive at the model level and pyperplan canonicalizes to
  lowercase, but the grader is case-sensitive. Do **not** blindly
  re-case against a first-seen-case map when no authority demands it;
  do **not** blindly emit planner-lowercase `str(p)` when the task
  example OR the task prose ("action/object names must match the PDDL
  domain/problem", "case-sensitive") promotes a case authority. Build
  a `case_map` from the highest-ranked case authority and apply it
  uniformly.
- **Ignoring "oddity" signals in your own reasoning.** If output
  disagrees with something you have already seen — underscored tokens
  where the example shows short verbs, split tokens where the example
  shows a long schema, parens where the example shows `verb(args)`,
  lowercase `airplane_cfbeg` where the problem file declares
  `airplane_CFBEG` — stop and reconcile against the source you
  observed. **Argument-count signal:** the number of comma-separated
  (or space-separated) args in your emitted `name(args)` line must
  equal the number of free parameters in that `:action`'s
  `:parameters` block in the domain. Airport `:action` has one free
  parameter (`?a - airplane`); if your output has 6 comma-separated
  args, the extra five are baked-in constants that must stay inside
  the head token — your schema split is wrong.
