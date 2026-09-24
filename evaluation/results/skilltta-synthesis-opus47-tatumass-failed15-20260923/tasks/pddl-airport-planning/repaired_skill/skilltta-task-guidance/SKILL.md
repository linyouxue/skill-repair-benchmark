---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the target task requires producing valid PDDL plans for a batch of planning problems described in a `problem.json` manifest, where each entry references a domain PDDL file, a problem PDDL file, and an output path for the plan. The airport domain (IPC) is notoriously large and combinatorial (Munich-scale instances), so brute-force LLM reasoning is unreliable — an external classical planner is the intended tool.

Before acting, gather:
- The exact schema of `problem.json` (keys `id`, `domain`, `problem`, `plan_output`) and confirm all listed files exist and are readable.
- The `:requirements`, predicates, action signatures, and object types declared in each domain file (airport domains typically use `:adl`, `:typing`, sometimes `:durative-actions` or numeric fluents).
- The `:objects`, `:init`, and `:goal` in each problem file so plan actions reference real, correctly-typed objects.
- Whether a classical planner (e.g., Fast Downward, FF, LAMA, ENHSP, pyperplan) is available on the system, and which search/heuristic configurations it supports.
- The exact plan output format expected by the evaluator — action-per-line, and whether the grader accepts standard IPC syntax `(action arg1 arg2)` or the parenthesized-with-commas style shown in the prompt's example.

## Possible Failure Modes
- Hand-writing a plan for large airport instances: the state space is enormous and hand-crafted plans will almost certainly be invalid or suboptimal to the point of failure.
- Ignoring the domain's `:requirements` — e.g., missing that the airport domain uses durative actions or conditional effects, causing planner selection mismatches.
- Using action-name or object-name casing/spelling that doesn't match the PDDL files (PDDL is case-insensitive in principle, but validators/graders may be strict).
- Emitting a plan in the wrong syntax. The example in the prompt uses `action(arg1, arg2)` style, but IPC-standard plans use `(action arg1 arg2)`. Check what the evaluator/VAL-style validator expects; when in doubt, mirror the format shown in the task prompt exactly.
- Writing plans to the wrong path — always use the exact `plan_output` string per entry, creating parent directories as needed.
- Silently skipping tasks that time out or fail to solve, leaving empty/missing output files, which can cascade into scoring 0 for those items rather than partial credit.
- Copying tactics or object names from retrieved examples: the retrieved examples in this payload are unrelated (pandas/pickle tasks) and contain no reusable PDDL content.
- Overwriting or corrupting the input domain/problem files, or other tasks' output files.
- Not handling airport-specific predicates carefully (e.g., `at-segment`, `blocked`, `occupied`, `facing`, direction constraints) — even a planner-generated plan can be rejected if the planner ignores non-standard extensions.

## Possible procedures
1. Parse `problem.json` and iterate task entries. For each: resolve absolute paths, verify files exist, and ensure the parent directory of `plan_output` exists.
2. Inspect the domain header (`:requirements`, `:types`, `:predicates`, `:action` or `:durative-action`) to pick an appropriate planner:
   - Classical STRIPS/ADL → Fast Downward (`--alias lama-first` or `seq-sat-lama-2011`) or FF.
   - Temporal/durative → a temporal planner (e.g., OPTIC, TFD) — but airport IPC classical track is usually non-temporal ADL.
3. Invoke the planner as a subprocess with a per-task time and memory budget. Capture stdout/stderr and the planner's output plan file (e.g., `sas_plan`, `sas_plan.1`, etc.).
4. Post-process the planner's plan into the required format:
   - Strip comments (`;`-prefixed lines) and blank lines.
   - Convert each action line to the format the evaluator expects. If the prompt's example uses `name(arg1, arg2, ...)`, transform `(name arg1 arg2)` accordingly; otherwise preserve IPC syntax. When ambiguous, prefer the syntax shown in the task prompt example.
   - One action per line, preserving order.
5. Write the transformed plan to `plan_output` (create dirs with `mkdir -p` / `os.makedirs(..., exist_ok=True)`).
6. Recovery strategy for hard instances:
   - Retry with a different planner/config or a longer timeout.
   - For very large Munich-scale instances, use a satisficing (not optimal) configuration; do not attempt optimal search.
   - If no planner is available, attempt a minimal correct plan only for the smallest instances by reading the goal and constructing action sequences that satisfy each goal literal, validating mentally against preconditions.
7. Validate each produced plan with VAL (`validate domain.pddl problem.pddl plan.txt`) if available, before moving on.
8. Log per-task success/failure but never abort the whole batch on a single failure — write whatever best-effort plan you have (or an empty file) and continue.

Decision points:
- If the planner returns "unsolvable," re-check parsing errors first — often a `:requirements` mismatch, not true unsolvability.
- If VAL rejects the plan, inspect which action's preconditions failed; this usually indicates a syntax translation bug in step 4, not a planning bug.

## Verification Checklist
- [ ] Every entry in `problem.json` has a corresponding non-empty file written at its exact `plan_output` path.
- [ ] Each plan file contains one action per line, with action and object names matching those declared in the referenced domain/problem PDDL files.
- [ ] Plan syntax matches the format shown in the task prompt example (or IPC standard if that is what the evaluator uses); parentheses, commas, and spacing are consistent.
- [ ] Plans have been validated (via VAL or an equivalent executor) against their domain+problem where feasible.
- [ ] No input PDDL files were modified; no unrelated files were touched.
- [ ] For any task that failed to solve within budget, a best-effort output file exists and the failure was logged; the batch was not aborted early.
- [ ] No content, names, or ids were copied from retrieved examples (which are unrelated to PDDL) into the plans.
- [ ] Output paths were created relative to the correct working directory, and existing outputs for other tasks were preserved.
