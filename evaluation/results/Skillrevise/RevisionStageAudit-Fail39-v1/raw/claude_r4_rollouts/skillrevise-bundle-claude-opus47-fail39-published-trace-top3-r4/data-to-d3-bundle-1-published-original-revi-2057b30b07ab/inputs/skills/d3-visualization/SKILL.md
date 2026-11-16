# D3 Visualization Skill

## Purpose
Produce D3.js visualizations (static or interactive) whose outputs land exactly where the verifier expects, with the library version and data wiring the task requires, and with a runtime self-check before finalizing.

## When to Use
Trigger when a task asks for a chart, plot, SVG, dashboard, or interactive data view built with D3. Covers both static diff-stable artifacts and interactive single-page apps (tooltips, selection, force layouts).

## Procedure
- Discover contract: read the task text and any provided scaffolding to extract (a) exact output paths and filenames, (b) required D3 major version, (c) data file locations and expected schema, (d) chart type and interactions, (e) static-vs-interactive mode. Echo these resolved values before writing code. If any item is ambiguous, pick a default and record it as a comment at the top of the main output file.
- Validate inputs: list the data files, inspect their columns/keys and row counts, and confirm the fields referenced by the chart contract exist. Stop and reconcile if a referenced field is missing.
- Source D3 deterministically (bounded fallback, in order): (1) use an existing local vendor copy if present; (2) use an offline mirror path if the environment provides one; (3) if network is permitted, fetch the pinned major version requested by the task to a local file; (4) if none work, fail loudly with a clear message. Never hardcode a version the task did not request.
- Implement in the correct mode:
- Static/diff mode: fixed width/height/viewBox, deterministic sort, no transitions, stable IDs, consistent numeric precision.
- Interactive mode: allow tooltips, hover, click selection, and force layouts, but seed any stochastic layout (fixed initial positions, fixed tick count) so the initial render is reproducible.
- Self-verify at task-specified paths: for every required output path, run an existence and readability check (e.g., `ls -la <path>` and read first bytes). Then load the HTML through a headless check (node + jsdom, a browser automation tool, or at minimum `grep` for required script tags and data references) to confirm the D3 script resolves, the data path resolves under the serving mode the verifier will use (fetch vs file://), and no obvious JS syntax errors exist. If a check fails, repair the specific cause (path, version, data wiring) before claiming done.
- Recover: if a check fails twice for the same cause, step back and re-run Discover; do not silently relocate outputs or swap versions.

## Constraints / Pitfalls
- Do not hardcode output directories (e.g., `dist/`), filenames, or D3 versions; always derive them from the task.
- Do not substitute a different D3 major version than requested; v6 and v7 differ in event signatures and modules.
- When the task implies `file://` loading, inline or co-locate data so `fetch` works without a server; when a server is implied, keep data external and reference by the declared path.
- Do not conflate determinism-for-diff with no-interactivity; interactive tasks need reproducible initial state, not absence of handlers.
- Do not claim completion without the existence check at the exact task-specified output paths and at least one runtime load check.
- Keep all source and comments in printable ASCII.