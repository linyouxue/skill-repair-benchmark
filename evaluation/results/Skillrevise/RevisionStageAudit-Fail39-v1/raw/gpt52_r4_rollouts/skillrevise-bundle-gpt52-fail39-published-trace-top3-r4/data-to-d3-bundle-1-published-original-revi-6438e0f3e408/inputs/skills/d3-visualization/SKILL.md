# D3 Deterministic Offline Visualization

## Purpose
Create verifiable, deterministic D3-based visualizations from local data files, producing self-contained artifacts that render offline and are saved exactly where the task/verifier will check.

## When to Use
Use when the task asks for a chart/plot/graph or data-driven SVG/HTML using D3, and the result must be reproducible (diffable) and work without external network dependencies.

## Procedure
- 1) Confirm requirements and outputs (no guessing).
- Extract: required output file paths (HTML/SVG/PNG) and any required D3 major version (for example, v6).
- If required output paths are not explicitly given, discover the expected output directory by listing the workspace and checking for conventions (for example, an existing output/ or dist/ used by other tasks). Do not invent new locations if the task likely checks a specific path.
- 2) Preflight environment constraints (before any irreversible work).
- Network: assume outbound network is blocked unless the task explicitly says otherwise.
- Dependency availability check (must pass one route):
- Route A (preferred): search the workspace for an existing D3 bundle (for example, d3*.min.js) and record its path and apparent version (from filename or header comment).
- Route B: check for a local JS dependency install (package.json plus lockfile and node_modules) and confirm D3 is present and matches the task-required major version.
- If neither route is available and network is not explicitly allowed: stop and request that the D3 bundle (correct major version) be provided locally, or that network access is permitted. Do not attempt curl/CDN fetches.
- 3) Load and validate input data deterministically.
- Confirm the data file(s) exist and are readable.
- Parse using a deterministic parser and explicitly handle types (numbers, dates).
- Establish a stable sort order for rows and for grouped keys (sort keys explicitly) before binding to marks.
- 4) Build the visualization with deterministic rendering rules.
- Fix width/height/margins and set viewBox explicitly.
- Avoid randomness and default transitions; do not rely on timing.
- Use stable IDs only when needed (for example, clip paths) and derive them from fixed strings.
- 5) Write artifacts to the required paths.
- Generate HTML that references only local assets (local D3 path) and local data (or embed data if the task forbids runtime file loading).
- Only create directories that are required to satisfy the task-specified output paths; otherwise reuse existing directories discovered earlier.
- 6) Verifier-aligned final checks (mandatory).
- Existence/readability: stat/ls each required output path and fail fast if any are missing.
- Offline dependency check: grep the generated HTML for remote URLs (http:// or https://); if present, replace with local references.
- If the page relies on runtime fetching of local data, do not claim file:// compatibility unless you have verified the serving method required by the task; otherwise, provide a minimal local-http serving instruction only if explicitly allowed/needed.

## Constraints / Pitfalls
- Never download D3 (or any dependency) from the network unless the task explicitly permits outbound network; do not add "fallback" behaviors that assume browser/file:// quirks without verifying them.
- Do not hard-code output folders (for example, dist/ or vendor/) or D3 versions; always follow the task-required version and exact output paths, or discover existing local conventions before creating new structure.