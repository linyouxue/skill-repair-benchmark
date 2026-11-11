# BLS Transit Period Search (Astropy) - Version-Robust Workflow

## Purpose
Find and validate periodic, box-shaped transit-like dips in a time-series light curve using astropy.timeseries.BoxLeastSquares (BLS), with a version-robust approach to compute_stats() so the workflow does not break across astropy releases.

## When to Use
Use when you have arrays (or table columns) for time and flux (optionally flux uncertainty) and the target signal is a repeating box-shaped dip (transit or eclipse). Do not use for general sinusoidal variability (use Lomb-Scargle) or when the task explicitly requires a different algorithm (for example TLS).

## Procedure
- 1) Discover inputs and environment (no assumptions yet)
- Identify where time, flux, and optional flux_err come from (arrays, table, file).
- Confirm astropy is available and importable; if not, stop and request installation or an allowed alternative.
- Evidence checkpoint: you can import BoxLeastSquares and can display basic shapes/dtypes and any units present.
- 2) Validate and sanitize the series before modeling
- Ensure time and flux lengths match, contain finite values, and include enough points to cover multiple expected events.
- Sort by time if not already sorted; remove NaN/inf rows consistently across all arrays.
- If units are not present, treat time as dimensionless but do not invent units; if units are present, keep them consistent.
- Evidence checkpoint: after cleaning, (a) time is strictly non-decreasing, (b) arrays have identical length, (c) no NaN/inf remain.
- 3) Run a conservative BLS search (grid discovery before customization)
- Create the model: BoxLeastSquares(time, flux, dy=flux_err if available).
- Choose a duration search range based on domain constraints (or a small set of plausible durations if unknown); prefer multiple durations rather than a single guessed value.
- Use model.autopower(durations, objective=...) for the first pass; only move to custom grids after you see peaks.
- Evidence checkpoint: periodogram arrays exist (period, power, duration, transit_time) and have consistent lengths; the maximum power index is computable.
- 4) Validate top candidates with compute_stats() using schema discovery (API-robust)
- Select the top N peaks by power (for example 5-10) and evaluate each candidate using model.compute_stats(period, duration, t0).
- Execution anchor (must do): inspect stats keys and normalize depth extraction:
- Record sorted(stats.keys()).
- If stats contains 'depth' as a tuple (depth, depth_err), unpack it.
- Else if stats has separate keys (for example 'depth' and 'depth_err'), use them.
- Only compute SNR if you can derive it reliably (depth_err exists and is nonzero); do not assume stats['depth_snr'] exists.
- Compute simple, version-stable checks using only discovered fields:
- Odd/even depth mismatch only if both depth_odd and depth_even exist; if those are tuples, compare their first elements.
- Transit count: if transit_times exists and is array-like, use len(stats['transit_times']); do not assume transit_count exists.
- Alias check decision point:
- For the best candidate period P, also evaluate 0.5*P and 2*P (within your searched period bounds) and compare power/stats side-by-side.
- Prefer the candidate with (a) strong power, (b) multiple transits, and (c) smaller odd/even mismatch when available.
- Evidence checkpoint: no KeyError from stats access; for each candidate you can report period, duration, t0, depth (and uncertainty if derivable), and transit count (if derivable).
- 5) Finalize and verify deliverables safely (only if the task requires writing output)
- Before writing any files, re-check the task instruction for required output path(s) and format; if unspecified, do not invent paths.
- Write only the explicitly required output(s) and immediately re-open/re-read them to confirm contents match the requested format.
- Evidence checkpoint: output file(s) exist at required path(s) and contain the selected period value in the required representation.

## Constraints / Pitfalls
- Do not hard-code compute_stats() field names like depth_err, depth_snr, or transit_count; always discover stats.keys() and branch on observed structure (for example depth as a tuple vs separate keys).
- Avoid irrelevant exploration: no plotting, no switching to TLS/Lomb-Scargle, and no installing extra packages unless explicitly requested by the task or required due to missing astropy.