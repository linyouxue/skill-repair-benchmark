# Prompt-First Verifier-Aligned Simulation Output Skill (Strict Paths, Schemas, Tool Preflight)

## Purpose
Produce verifier-consumable simulation artifacts by treating the task prompt as the primary contract, performing environment/tooling preflight to prevent runtime stoppages, writing only to verifier-visible output paths, and hard-gating completion on exact path existence plus reload-based schema checks.

## When to Use
Use this skill when a benchmark/verifier grades your work by checking for specific artifacts (files) at specific paths with strict schemas or numeric constraints, and when the runtime environment may differ from local assumptions (interpreter name, missing libraries, plotting failures).

## Procedure
- 1) Extract the observable contract (prompt-first; tests second)
- Parse the task prompt and record as a checklist:
- Required output root path pattern (exact path if given).
- Required artifact filenames and formats (json/csv/png/etc).
- Any stated schema requirements (required keys/columns, types, array shapes, required precision/format).
- Any stated numeric thresholds/constraints (only those explicitly stated).
- Whether extra artifacts are allowed; if not specified, assume "do not add extra files".
- Optional refinement (only if present): locate and read verifier/tests scripts to confirm paths, filenames, and schema rules. If absent, do not invent rules.
- 2) Environment and tool preflight (fail fast before running long jobs)
- Interpreter gate:
- Check available Python entrypoints (e.g., try `python3 --version`, then `python --version`), select one that works, and use it consistently.
- If no Python works, stop and report the missing tool (do not proceed with partial outputs).
- Dependency gate:
- Run a short import smoke test for required libs (minimum: the language stdlib; plus any libs you will actually use).
- Plotting safety: force a non-interactive backend and run a tiny plot write test.
- Execution anchor: write a throwaway PNG under the required output root (or a temporary subdir under it) and verify it exists and is readable. If this fails, fix backend/permissions/path issues before any simulation.
- 3) Discover inputs and validate schemas before simulation
- Identify required input files from the prompt; if multiple candidates exist, list them and select deterministically (document the rule).
- Validate each required input is readable and matches the prompt-declared schema/format (parse and check required fields).
- If any critical input/schema requirement is ambiguous or missing, stop and request clarification rather than guessing hidden verifier rules.
- 4) Execute the minimal compliant computation (bounded, contract-driven)
- Implement only what is needed to satisfy the prompt/verifier contract (do not add optional behaviors or extra outputs).
- Keep computation bounded:
- If tuning/iteration is required, cap iterations and keep a safe fallback configuration.
- If NaN/Inf occurs, stop the run, adjust the smallest lever (e.g., smaller dt, stronger saturation), and rerun at most once.
- If plotting is required by the contract:
- Wrap plot generation so that mathtext/tight-layout/font issues cannot crash the run.
- If a plot fails, regenerate a simpler plot (plain labels, no mathtext, no tight layout) that still meets the required file presence/format.
- 5) Write artifacts to the verifier-visible path and hard-gate on reload checks
- Write outputs only under the exact required output root. Never silently switch to another directory if writing fails; instead inspect permissions/mounts and fix the root cause.
- Do not create extra files beyond the declared artifact list unless the contract explicitly allows extras.
- Execution anchor (final gate):
- For each required artifact path: assert it exists, is readable, and non-empty.
- Reload each artifact and validate against the prompt/verifier schema checklist:
- JSON: required keys present; types match (numbers as numbers, arrays as arrays); shapes/lengths match declared expectations.
- CSV: required columns present; row counts and types match expectations.
- Images: file readable and non-empty (and optionally loadable if a lightweight loader is available).
- Validate numeric sanity required by the prompt: finite values; enforce only explicitly stated thresholds.
- If any check fails, fix the smallest scope issue (path, filename, serialization, schema) and rerun only the necessary steps (prefer re-write + re-validate over rerunning the full simulation).

## Constraints / Pitfalls
- Do not treat repo discovery as the primary contract source; the task prompt is authoritative unless a visible verifier/test explicitly overrides or refines it.
- Do not output extra artifacts, alternate filenames, or alternate directories unless the contract explicitly permits them; the final completion gate must validate exact required paths and reload-based schema assertions before claiming success.