# SKILL.md

## When to use
Use this skill when you are given a planning benchmark task that provides:
- A **PDDL domain file** and a **PDDL problem file** (paths referenced from a `problem.json` list), and
- A required **plan output path** where you must write a plan.

Before acting, gather evidence by:
- Opening `problem.json` and enumerating each task entry’s `domain`, `problem`, and `plan_output` paths.
- Reading the domain/problem PDDL to confirm: action names/parameters, objects, initial state, and goal conditions.
- Identifying any format constraints for the plan (e.g., one action per line, exact symbol spelling).

## Possible Failure Modes
- **Wrong plan syntax**: using commas/spacing/parentheses inconsistently with expected plan grammar; putting multiple actions on one line.
- **Name mismatches**: action or object identifiers in the plan don’t exactly match the PDDL files (case, hyphens/underscores, parameter order).
- **Invalid plan**: plan violates action preconditions, misses required ordering constraints, or fails to achieve all goals.
- **Ignoring multiple instances**: processing only one entry from `problem.json` instead of generating plans for all entries.
- **Writing to wrong location**: not writing the plan to `plan_output`, or leaving it empty/with extra commentary.
- **Hidden state leakage**: overwriting unrelated files or changing repository state beyond generating the required plan outputs.
- **Assuming facts from retrieved examples**: copying any concrete identifiers, paths, or numbers from other tasks rather than deriving everything from the current PDDL inputs.

## Possible procedures
1. **Enumerate tasks**
   - Parse `problem.json` as a list of task dictionaries.
   - For each entry, confirm the domain/problem files exist and are readable; create parent directories for `plan_output` if needed.

2. **Parse and understand the PDDL**
   - From the **domain**: list action schemas, parameters, preconditions, effects; note typing and any numeric/temporal features if present.
   - From the **problem**: collect objects, init facts, and goals.
   - Decision point: if the PDDL uses advanced features (e.g., derived predicates, numeric fluents), choose a planning approach/tool that supports them.

3. **Select a planning approach**
   - Prefer a reliable planner available in the environment (if permitted) that can ingest PDDL and output a plan.
   - Otherwise implement/compose a planner strategy appropriate to the domain (e.g., forward search with heuristics).
   - Recovery check: if the first attempt fails, re-check parsing, typing, and whether any requirements/constraints were missed.

4. **Construct the plan text in the required format**
   - Output strictly as action applications, **one per line**.
   - Use the **exact action name and object tokens** from the PDDL.
   - Keep a consistent formatting convention (commonly `action arg1 arg2 ...` or `action(arg1, arg2, ...)`) matching what the benchmark expects; ensure you do not mix formats within a file.

5. **Write outputs safely**
   - Write each plan to its `plan_output` path with no extra logs, headers, or explanations.
   - If you validate by reloading or re-reading files, do so without modifying inputs (treat domain/problem as read-only).

## Verification Checklist
- [ ] For every entry in `problem.json`, a plan file exists at the specified `plan_output` path.
- [ ] Plan file contains **only** action lines (no commentary), with **one action per line**.
- [ ] Every action name and object name used appears in the domain/problem PDDL exactly (spelling/case/ordering consistent).
- [ ] Plan is **valid**: each step’s preconditions are satisfied at execution time; applying all steps achieves the full goal.
- [ ] No accidental dependency on retrieved examples (no copied identifiers/paths/facts); all symbols come from the current PDDL inputs.
- [ ] No unrelated files were altered; only the intended plan outputs were created/updated.
- [ ] If any planner/run failed, you have a recovery attempt recorded in your process (re-check PDDL requirements, typing, and output formatting) before finalizing.
