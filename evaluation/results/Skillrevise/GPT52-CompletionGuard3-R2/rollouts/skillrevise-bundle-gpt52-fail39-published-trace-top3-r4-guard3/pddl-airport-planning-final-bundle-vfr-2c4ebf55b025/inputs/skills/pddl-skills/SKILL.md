# PDDL Plan Synthesis and Verifier-Aligned Output

## Purpose
Generate, validate, and write classical sequential plans for PDDL domain/problem pairs while aligning artifacts (paths and text format) with the external task harness/verifier rather than relying only on internal library conventions.

## When to Use
Use this procedure whenever you must produce a plan file (or set of plan files) that will be scored by an external checker (e.g., benchmark harness, autograder, CI verifier) and where tool availability, required output paths, and exact plan-text syntax may differ from your preferred planning library.

## Procedure
- 1) Discover the execution environment and output contract (no planning yet).
- Identify the required output path(s) from the task instruction, harness config, or provided template files. If no path is explicitly given, discover the expected output location by listing the current working directory and any mounted output directories (do not guess a new location).
- Discover available tools in this order (record what you find):
- Repo-provided scripts (e.g., validate.py, run_planner.sh, check_plan.*, any README describing evaluation).
- CLI planners/validators available on PATH (probe with safe "help/version" calls).
- Python libraries (probe by import) such as unified_planning; do not assume they exist.
- Decision point: choose one primary route and one fallback route (bounded to one fallback) based on what is actually present.
- 2) Load and sanity-check inputs before generating a plan.
- Confirm domain and problem files exist, are readable, and look like PDDL (non-empty; contain "(define").
- Parse using the chosen toolchain:
- If using a repo script/validator, follow its required invocation and expected file naming.
- If using a Python library, parse with that library but do not commit to its default plan serialization yet.
- Checkpoint: if parsing fails, stop and report the parse error and the exact file paths used; do not proceed to planning.
- 3) Generate a plan with bounded recovery.
- Run the primary planner route with an explicit timeout (use the environment/default task timeout; otherwise choose a conservative timeout and record it).
- If the primary route fails due to missing tool, crash, or unsupported features:
- Execute exactly one fallback route (closest available alternative) and re-run only the minimal steps needed (re-parse if required, then re-plan).
- Decision point (unsolvable vs failure):
- If the planner reports "no plan" (unsolvable), produce the task-required "no plan" representation only if explicitly specified; otherwise produce an empty plan file and label it as unsolved (do not claim validity).
- If the planner fails (tool error), stop and surface the error; do not emit a guessed plan.
- 4) Validate and serialize in a verifier-aligned way, then confirm artifacts at the exact output paths.
- Validation:
- Prefer the same validator the harness uses (repo-provided checker). If available, run it against the candidate plan text you will write.
- If only an internal validator is available, run it but treat results as "internal-only" and do not claim verifier acceptance.
- Serialization (plan text schema enforcement):
- Write plain ASCII text, one grounded action per line, with no extra commentary, headers, step numbers, or timestamps unless the harness explicitly requires them.
- Do not use library default stringification (e.g., str(action)) unless you have verified (by the harness checker or documented format) that it matches the required plan syntax.
- Execution anchor (mandatory final check):
- After writing, verify at the exact required output path(s): file exists, is readable, and content matches the enforced schema (line-based actions). If validation tooling exists, re-run validation on the written file (not in-memory objects).
- If the file is missing or not readable at the required path, inspect permissions/mounts and fix the write location; do not silently switch to a different directory.

## Constraints / Pitfalls
- Never claim "VALID" unless validation is performed with a verifier-equivalent tool (repo/harness checker) on the exact written artifact; otherwise state "internally validated by <tool>" and treat verifier acceptance as unknown.
- Do not hard-code planners, Python packages, output directories, or action string formats. Select tools and output paths only after discovery, and always end with an existence/readability check at the task-specified output path(s).