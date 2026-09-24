# transit-period-determination-from-lightcurves

## Purpose
Determine an exoplanet orbital period from a photometric light curve by applying minimal, transit-preserving cleaning and detrending, running a transit-specific period search (TLS/BLS), validating against common aliases (P/2 and 2P), and writing a verifier-aligned period artifact.

## When to Use
Use when the task requires selecting a single best orbital period (in days) from time-series flux data that may contain outliers, gaps, quality flags, and stellar/instrument trends, and when you must justify the selected period against half/double-period aliases before writing it to a specified output path.

## Procedure
- 1) Discover inputs, tools, and task contract (no assumptions)
- Identify: where the light curve comes from (file, table, API), which columns exist (time/flux/flux_err/quality), and the required output path and formatting (eg 5 decimals).
- Check available libraries at runtime (prefer: lightkurve for LC handling; TLS if installed; otherwise astropy.timeseries.BoxLeastSquares for BLS).
- Checkpoint evidence: you can print/inspect a small schema summary (column names, dtypes, n_rows) and confirm the output path string from the task.
- 2) Validate and standardize the light curve (before any filtering)
- Ensure time is strictly increasing; if not, sort by time.
- Mask invalid rows: finite(time, flux) and (if present) finite(flux_err) and flux_err > 0.
- If a quality/flag column exists, discover its convention:
- If documentation/metadata states "0 means good", filter quality == 0.
- If unknown, do not guess; instead compare basic diagnostics (fraction removed, RMS of remaining flux, and presence of obvious artifacts) for common conventions and choose the one that yields fewer obvious discontinuities without removing most data. If still ambiguous, keep all points and proceed with robust outlier handling.
- Checkpoint evidence: report n_points before/after masks and the inferred/used quality rule (or "unknown, not applied").
- 3) Transit-preserving cleaning and detrending (avoid destroying the signal)
- Outliers: apply robust clipping that minimizes transit suppression:
- Prefer a running-median residual clip or library outlier removal that operates on detrended residuals (two-pass approach: light clip -> detrend -> clip).
- Use conservative thresholds first; only tighten if diagnostics show clear non-astrophysical spikes.
- Detrending: remove long-timescale variability while preserving short transits:
- Choose a detrend scale based on discovered cadence and expected transit duration scale; enforce that detrend window >> expected transit duration and << overall baseline.
- If using lightkurve flatten/SG or spline, avoid fixed window literals; derive window length from cadence and a target timescale.
- If you already have candidate transit times from a search, re-detrend with transit masking around those events and re-run the search once (single refinement pass).
- Checkpoint evidence: report detrend parameters (derived window/timescale) and a before/after robust scatter metric (eg MAD or RMS) to show cleaning did not collapse variability unrealistically.
- 4) Run a transit-specific period search with environment-grounded bounds
- Set search period bounds from data, not guesses:
- max_period: at most ~1/2 to 2/3 of the time baseline (to ensure multiple transits), unless the task explicitly allows single-transit inference.
- min_period: at least a few cadences and above the effective time resolution; avoid searching below what cadence can support.
- Execute TLS if available; else run BLS (astropy) with an appropriate duration grid derived from cadence and typical transit fractions (do not hard-code a single duration).
- Extract top candidate periods (at least the best and a few runners-up) for validation.
- Checkpoint evidence: store/print the best periods and their objective scores (TLS SDE or BLS power/SNR) and confirm the search grid bounds used.
- 5) Validate candidates and select the final orbital period (explicit decision rule)
- For the top candidate period P0, evaluate alias/harmonic set: {P0/2, P0, 2*P0} (and optionally nearby peaks if scores are close).
- For each candidate Pc in the set:
- Fold and bin the light curve; compute:
- Odd-even transit depth difference (split transits by epoch parity). Prefer small odd-even differences relative to depth uncertainty.
- Number of distinct transits observed across the baseline (prefer >= 2 when possible and consistent spacing).
- Consistency of transit shape and depth across events (no single-event dominance unless baseline only allows it).
- Search score at/near Pc (compare TLS/BLS metric across candidates, not just visual impression).
- Decision rule:
- Choose the Pc with (a) strong search score and (b) best odd-even consistency and (c) the most plausible transit count/spacing given the baseline.
- If P and 2P are close in score, prefer the one where the folded curve shows a single distinct transit per orbit (2P) rather than alternating unequal depths at P (indicative of eclipsing-binary-like odd/even effects).
- If ambiguity remains after metrics are computed, do not invent precision; report the ambiguity in logs and select the candidate with the most stable metrics across a small range of detrend windows (sensitivity check).
- Checkpoint evidence (execution anchor): produce a small table for P/2, P, 2P with (score, odd_even_diff, n_transits) and clearly state chosen_period and why.
- 6) Write the required artifact and verify it (no silent path changes)
- Write exactly one numeric value (days) to the task-specified output path. Apply 5-decimal formatting only if the task requests it; otherwise write full precision reasonably.
- Immediately verify:
- File exists at that exact path.
- Reading the file yields exactly one parseable float and an optional trailing newline.
- If writing fails, investigate permissions, working directory, and mount availability; do not redirect to a different path unless the task explicitly allows it.
- Checkpoint evidence (execution anchor): existence/read-back checks pass and the parsed float equals the intended chosen_period within formatting tolerance.

## Constraints / Pitfalls
- Do not use aggressive iterative sine fitting / multi-iteration harmonic removal when searching for transits; it can remove the planetary signal and create false confidence. Only consider periodic stellar-variability modeling if it is strictly masked away from transits and validated by re-detecting the same period afterward.
- Do not hard-code detrend window lengths, period bounds, durations, or output paths. Derive bounds from cadence and baseline; use the exact output path provided by the task/verifier and confirm by read-back before finishing.