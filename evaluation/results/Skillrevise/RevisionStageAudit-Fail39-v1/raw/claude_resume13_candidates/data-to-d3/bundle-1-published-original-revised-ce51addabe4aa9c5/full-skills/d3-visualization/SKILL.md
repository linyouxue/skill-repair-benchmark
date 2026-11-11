# D3 Visualization

## Purpose
Produce D3-based data visualizations (static or interactive) whose outputs land at the exact paths, use the exact library version, and satisfy the exact feature requirements declared by the task. The skill emphasizes discovery, conditional determinism, and post-write verification over fixed defaults.

## When to Use
Use when the task requests a chart, plot, interactive data visualization, force layout, map, or any data-driven SVG/HTML artifact produced with D3. Do not use for plain tables or markdown summaries.

## Procedure
- Discover contract: read the task text and extract (a) required D3 major version, (b) output root and file tree (e.g., index.html, js/, css/, data/), (c) input data files and their columns, (d) interactive vs. static requirement, (e) any explicit acceptance signals (row counts, suppression rules, linked selection, tooltip rules). Record these as a short header comment in the main HTML/JS file. If any item is unspecified, pick a documented default and note it.
- Validate inputs: confirm each referenced data file exists and that required columns are present (e.g., head the CSV/JSON and assert field names). Confirm the output directory is writable; create the declared subtree only (do not invent dist/ or vendor/ unless the task says so).
- Choose library source (bounded fallback): (1) if a local vendored D3 at the required major version is present, use it; (2) else, if the task permits network, fetch D3 at the required version once and save it under the task's declared asset path, then reference the local copy; (3) else, stop and surface the conflict rather than silently switching versions or sources.
- Apply conditional determinism: if the task calls for static/reproducible output, enforce stable sort order, fixed width/height/viewBox, no randomness, no transitions, stable IDs, consistent numeric precision. If the task calls for interactivity, force simulation, or animation, prioritize task fidelity; still remove gratuitous randomness and keep IDs stable where feasible.
- Implement: write code directly into files (avoid interactive REPL/heredoc traps). Keep interaction patterns minimal: a single tooltip div toggled via a CSS class with pointer-events:none, and selection via class toggles. Honor any conditional interaction rules the task states (e.g., suppress tooltip for a specific category, link selection between views).
- Verify (execution anchor): after writing, run existence checks on every task-declared output path; run a syntax check on JS files (e.g., `node --check` if available); if a headless browser is available, load the HTML and assert the task's observable acceptance signals (expected number of rendered marks, presence of legend/axes, correct suppression rules, bidirectional selection). Enumerate each task-stated signal and confirm it before declaring done.
- Recover: if a check fails, inspect the failure signal (missing file, wrong path, parse error, missing mark count) and repair the smallest responsible unit; do not relocate outputs to a different path to make a check pass.

## Constraints / Pitfalls
- Do not hard-code library version, output directory, or file layout. Derive them from the task; use documented defaults only when the task is silent.
- Do not apply static-chart determinism rules (no animation, no randomness, fixed ticks) to tasks that explicitly request interactivity, force layouts, or animated transitions.
- Do not declare completion without verifying that every task-declared output path exists and every task-stated acceptance signal is observable in the rendered artifact.
- Do not silently violate an offline or version constraint; if the planned source is unavailable, follow the bounded fallback and record the choice, or stop and surface the conflict.
- Keep interaction code minimal and inline; avoid pasting large boilerplate that does not match the task's specific interaction rules.
- Avoid persistent REPL sessions for file authoring; write files directly and re-check from a clean shell state.