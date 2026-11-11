# Reflow Profile Compliance Toolkit (Checkpointed)

## Purpose
Compute deterministic reflow-profile compliance metrics (for example ramp rate, time above liquidus, peak margin, and feasibility) from time-temperature thermocouple traces and handbook-defined limits, and emit verifier-visible JSON artifacts with strict validation.

## When to Use
Use when a task requires extracting numeric limits/definitions from a handbook PDF (or equivalent spec text) and computing run-level metrics from thermocouple time series, producing one or more JSON files that will be checked by an external verifier.

## Procedure
- 1) Discover environment and deliverables (do not assume)
- Identify the required output filenames and exact required output directory from the task text; if unspecified, discover standard mounts by listing likely roots (for example /app, current working directory) and locate writable output locations.
- Check that input data files exist and are readable (for example CSVs and a handbook PDF); record their discovered paths.
- Execution anchor: perform a write-read smoke test in the intended output directory (create the directory only if it is the task-specified mount). Evidence: the test file can be written and read back.
- 2) Extract handbook constraints with tool fallbacks (fail fast, or branch)
- Determine available PDF-to-text method in the environment:
- Prefer a system tool if present (for example pdftotext).
- Else prefer a Python library if importable (pdfplumber, then pypdf).
- Else do not guess limits; mark extraction as failed.
- Extract text to a temporary text file and validate extraction quality:
- Evidence checkpoint: extracted text is non-empty and contains at least one expected keyword relevant to the metrics (for example "ramp", "slope", "TAL", "liquidus", "peak", "conveyor").
- Parse a compact constraints object from the extracted text:
- Required fields should be explicit and machine-usable (numbers in consistent units, regions defined as temp/time/zone bands, margins/windows).
- Decision point:
- If extraction or parsing fails, do not continue with fabricated limits. Either (a) stop with a clear error, or (b) proceed to compute raw metrics only and set a machine-readable flag like handbook_extraction_failed=true in every output object so the verifier-visible artifacts still exist.
- 3) Load and validate input tables before computing
- Load thermocouple time series and run metadata using an available toolchain:
- Prefer Python + pandas if available; otherwise use csv tooling available in the environment.
- Validate required columns exist before computing anything:
- Thermocouple table: run identifier, thermocouple identifier, time (seconds or discoverable units), temperature (C or discoverable units).
- Metadata table: run identifier and any fields needed to determine liquidus or product family (only if required by constraints).
- Normalize IDs to strings; sort deterministically by (run_id, tc_id, time).
- Strictly ignore segments with non-increasing timestamps (dt <= 0) rather than trying to "fix" time.
- 4) Compute metrics deterministically (no hidden heuristics)
- Ramp rate (max slope) in the configured region:
- Compute finite-difference slopes on consecutive samples with dt > 0.
- Apply region filtering using the constraints object (temp band: both endpoints inside; time band: endpoints within; zone band: only if zone id exists and is validated).
- Time above threshold (for TAL/wetting):
- Use linear interpolation per segment to compute crossing times; do not approximate by sample counting.
- Peak and margins:
- Per TC compute peak as max(temp).
- When reducing to a run-level value, use deterministic tie-breaks:
- For maxima: choose highest value, then smallest tc_id.
- For minima: choose lowest value, then smallest tc_id.
- If required inputs for a metric are missing (no samples, no valid segments, missing threshold), output null for that metric and do not claim compliance.
- 5) Construct and write outputs to verifier-visible paths
- Determine the exact set of required JSON outputs (names and count) from the task; do not invent extra files.
- Output rules:
- Use stable ordering for lists and dictionary keys (sort by run_id, tc_id, etc.).
- Round floats consistently (for example 2 decimal places) and serialize invalid numbers (NaN/Inf) as null.
- Include explicit flags for missing handbook constraints or missing data when applicable.
- Write each JSON artifact to the exact required path (do not redirect to a different folder).
- 6) Post-write verification (must pass before completion)
- Execution anchor: for each required output path, assert:
- File exists at the exact path and is readable.
- JSON parses successfully when reloaded.
- No NaN/Inf values remain after serialization (null only).
- If the task specifies required top-level keys or shapes, assert them here (do not assume unspecified schemas).

## Constraints / Pitfalls
- Never fabricate handbook limits or "cfg" values. If the handbook cannot be extracted/parsed with available tools, either halt or emit outputs with null metrics plus an explicit handbook_extraction_failed flag; do not silently proceed as if compliant.
- Do not hard-code paths, tool names, file names, units, or schemas unless they are explicitly provided by the task. Always discover inputs/outputs first, and always verify the exact required output paths by reopening the files after writing.