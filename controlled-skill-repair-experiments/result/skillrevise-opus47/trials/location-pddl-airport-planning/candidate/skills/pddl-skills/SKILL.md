---
name: pddl-skills
description: "Utilities for solving IPC-style PDDL tasks: read task entries from problem.json, parse domain/problem, synthesize a plan, and write a text plan whose lines match the domain's lifted action schema expected by the task verifier."
license: Proprietary. LICENSE.txt has complete terms
---

# Scope

Each task in `problem.json` provides `domain`, `problem`, and `plan_output`.
For every entry: load domain + problem, produce a plan, write it to
`plan_output` in the exact line format the verifier parses from the raw PDDL
domain. Do not assume any specific planner is installed; discover what is
available in the environment.

# Verifier-visible Output Contract (hard constraints)

The written plan file is parsed against the original PDDL domain, not against
any planning library's internal plan object. Enforce all of the following for
every non-empty, non-comment line of `plan_output`:

1. Line form: `<action_name>(<arg1>, <arg2>, ..., <argN>)`.
   - `action_name` must be a lifted action symbol declared via `(:action
     action_name ...)` in the referenced domain file. It must NOT be a
     grounded/compiled identifier that fuses parameters into the name
     (e.g. `move_seg_x_y_south_south_medium`).
   - Arguments are a comma-separated list in the order of the action's
     `:parameters`. Each argument token must be an object declared in the
     problem's `:objects` or a constant declared in the domain.
   - Arity N must equal the parameter count of that `:action`.
2. One action per line, in execution order, starting from the problem's
   `:init` state.
3. Plain ASCII text, UTF-8 encoded, Unix newlines. No surrounding commentary,
   no PDDL `(` list syntax, no step indices, no cost annotations.
4. An empty plan is written as an empty file (only acceptable if the goal
   already holds in `:init`).

Treat (1)-(3) as the acceptance oracle. Any library-internal validator is
advisory only.

# Workflow (ordered checkpoints)

For each task entry in `problem.json`:

## C1. Discover inputs
- Read `domain`, `problem`, `plan_output` from the entry.
- Confirm both PDDL files exist and are readable; otherwise record a failure
  for this entry and continue to the next.
- Ensure the parent directory of `plan_output` exists; create it if missing.

## C2. Parse the domain's action schema (independent of any planner)
- From the domain file, extract for each `(:action NAME :parameters (?a - T
  ?b - T ...) ...)`:
  - the lifted `NAME`,
  - the ordered parameter list and arity.
- Keep this `action_schema` map (NAME -> arity, parameter types). It is the
  ground truth used both to post-process the planner output and to validate
  the written file.
- From the problem file, extract the set of declared objects (plus domain
  constants) to validate argument tokens.

## C3. Discover an available planner
- Probe the environment for a usable classical planner. Prefer, in order:
  1. A planner that natively emits lifted actions in the form
     `name arg1 arg2 ...` or `name(arg1, ...)` (e.g. Fast Downward,
     downward, fd, lama, ff, Madagascar, scorpion, or a system-installed
     `planutils` tool).
  2. A Python planning library (e.g. `unified_planning` with any backend
     such as `fast-downward`, `tamer`, `enhsp`, `pyperplan`).
- Record which route is used. Do not hard-code a specific planner; use
  whatever the environment exposes. If no planner is available, write no
  file for this task and report the failure.

## C4. Generate a plan
- Invoke the chosen planner with the domain and problem.
- Capture its action sequence, whether as text output or as a structured
  plan object.

## C5. Normalize to lifted form (mandatory before saving)
Many backends (notably pyperplan-style grounding) return action identifiers
that fuse parameter values into the name and expose only a subset of
parameters. The written file must reverse that:

- For each action produced by the planner, determine `(name, args)` such
  that `name` is a key of `action_schema` and `len(args)` equals the
  recorded arity.
- Resolution strategies, in order:
  1. If the planner exposes a lifted action object with the original
     operator name and parameter bindings, use them directly.
  2. Otherwise parse the raw identifier against `action_schema`: find the
     longest declared `NAME` that is a prefix of the identifier (respecting
     an underscore boundary); split the remaining underscore-separated
     tokens into exactly `arity(NAME)` arguments. Combine with any
     explicitly bound parameters so the final argument list matches the
     declared `:parameters` order.
  3. If resolution is ambiguous or arity cannot be matched, do not save a
     malformed line; abort this task with a failure note.
- Verify each resolved argument token appears in the problem's objects set
  or the domain's constants.

## C6. Write the plan file
- Write one line per action in the exact form
  `name(arg1, arg2, ..., argN)` (comma + single space between arguments) to
  `plan_output`. No header, no trailing commentary.

## C7. Reload-and-assert (execution anchor)
- Reopen `plan_output` from disk.
- For every non-empty line, assert all of:
  - matches regex `^[A-Za-z0-9_-]+\(([^()]*)\)$`,
  - the leading name is a key of `action_schema`,
  - the comma-separated argument count equals that action's arity,
  - every argument token is in the declared objects/constants set.
- If any assertion fails, do not leave the broken file in place: either
  repair via C5 and rewrite, or remove the file and record failure.

## C8. Optional semantic check
- If a validator (e.g. VAL `validate`, or a library validator) is available,
  run it against the domain, problem, and written file. Treat its result as
  advisory; the line-format contract in C7 is the gating check.

# Fallbacks

- No planner available: skip plan generation for the task and continue; do
  not fabricate action sequences.
- Planner times out or returns no plan: write no file (or an empty file only
  if `:init` already entails `:goal`); never emit placeholder actions.
- Grounded-name resolution fails for a step: fail the task rather than
  write a line whose `name` is not in `action_schema`.
- Paths from `problem.json` are relative: resolve them against the directory
  containing `problem.json`.

# Anti-patterns (do not do)

- Do not hard-code any particular backend (e.g. "always use pyperplan").
- Do not use a library's `PDDLWriter` or internal plan `__str__` directly
  as the save step without first checking that each emitted line satisfies
  C7; many writers emit grounded or parenthesized forms that the verifier
  rejects.
- Do not treat a library's internal `PlanValidator` result as proof of
  acceptance; it validates against the library's compiled model, not the
  raw domain the verifier reads.
- Do not include step numbers, costs, `;` comments, or wrap lines in extra
  parentheses.