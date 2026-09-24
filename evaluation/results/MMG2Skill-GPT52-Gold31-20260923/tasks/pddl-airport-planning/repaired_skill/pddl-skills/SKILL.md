---
name: pddl-skills
description: Automated Planning utilities for loading PDDL domains/problems, generating
  and validating sequential plans, and writing action-per-line plan files for each
  entry in `problem.json`.
license: Proprietary. LICENSE.txt has complete terms
---

## Steps
1. **Read the task list**
   - Open `/app/problem.json` and iterate over each task entry with keys: `domain`, `problem`, `plan_output`.
2. **Load domain + problem (Unified Planning)**
   - Use `unified_planning.io.PDDLReader()` to parse:
     - `domain_path = task["domain"]`
     - `problem_path = task["problem"]`
   - Fail fast if parsing errors occur.
3. **Generate a plan (Pyperplan via OneshotPlanner)**
   - Use `unified_planning.shortcuts.OneshotPlanner(name="pyperplan")`.
   - Call `planner.solve(problem)` and require a solved status (e.g., `SOLVED_SATISFICING`) and a non-`None` plan.
4. **Validate the plan**
   - Use `unified_planning.shortcuts.SequentialPlanValidator(problem_kind=problem.kind)` and validate the generated plan against the problem.
   - Only proceed to writing if the validator returns `VALID`.
5. **Write the plan file exactly as required**
   - Create directories for `task["plan_output"]` if needed.
   - Write **one action per line**, matching the domain’s action/object names (typically `action_name(param1, param2, ...)` as printed by the plan).
   - Do not add extra formatting beyond the per-line action strings.
6. **Tool / shell execution constraint (when running in a terminal tool)**
   - **Do not submit multiple separate commands in one tool call.** Run them as separate tool calls, or chain them in a *single* shell command.
   - If chaining with `&&`, keep it on the **same line** as the preceding command (never start a new line with `&&`, including after a heredoc terminator).
7. **Verify outputs**
   - Confirm each `plan_output` file exists and contains the expected number of action lines (e.g., via `ls -la` and `cat` in separate tool calls or a correctly chained single command).
## Expected Result
- For every entry in `/app/problem.json`, a corresponding plan file is created at `plan_output`.
- Each plan file contains a **valid** sequential plan with **one action per line**, using action/object names that match the given PDDL domain and problem.
- No terminal/tool errors due to bundling multiple commands or malformed `&&` chaining.
