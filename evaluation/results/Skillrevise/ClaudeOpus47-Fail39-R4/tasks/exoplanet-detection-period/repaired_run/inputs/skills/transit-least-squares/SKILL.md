# transit-least-squares

## Purpose
Deterministic workflow for detecting a single transiting-exoplanet signal in a light curve using Transit Least Squares (TLS), with explicit checkpoints that resolve period aliasing (P vs P/2 vs 2P) and validate detrending against stellar activity before any period is finalized.

## When to Use
Use when the task is to recover the orbital period (and optionally T0, depth) of a transit-shaped signal from a time-flux-flux_err light curve. Do not use for general periodicity (rotation, pulsation, eclipsing binaries), for multi-planet discovery pipelines, or when the task already supplies a trusted period. Only fires when the alias and odd/even checks below would change the reported period.

## Procedure
- Discover inputs: confirm arrays `time`, `flux`, `flux_err` exist and are finite; if `flux_err` is missing, estimate it from a running MAD and record this fallback. Note expected transit duration if provided or estimate it from any prior candidate.
- Preprocess: remove outliers (sigma clipping, start at sigma=3), then detrend/flatten. Choose detrending window `W` such that `W >= 3 * expected_transit_duration` and `W <= 0.3 * dominant_activity_timescale`. If these inequalities cannot both hold, record a conflict and iterate W; prefer the larger W that still preserves transit depth (check that injected or candidate transit depth is not reduced by more than ~10%).
- Broad TLS search: run `transitleastsquares(time, flux, flux_err).power(...)` over a broad period range appropriate to the dataset baseline. Record `period`, `SDE`, `snr`, `T0`, `depth`.
- Alias resolution checkpoint (MANDATORY, hard gate):
- Re-run TLS constrained to narrow windows around `P`, `P/2`, and `2*P` (e.g., +/- 2 percent each).
- Record `SDE_P`, `SDE_half`, `SDE_double`.
- Decision rule: pick the period among `{P, P/2, 2P}` with the strictly highest SDE. On ties within 1 unit of SDE, prefer the longer period (TLS half-period aliases are the common failure mode when transits are missed in gaps).
- Odd/even checkpoint (MANDATORY, hard gate):
- Phase-fold at the alias-resolved period; measure in-transit mean depth separately for odd-numbered and even-numbered transits.
- Require `|depth_odd - depth_even| <= max(1 * combined_sigma, 0.2 * depth)`. If this fails, the signal is likely a half-period alias of an eclipsing-binary-like pattern; double the period and re-run the odd/even check once.
- Independent cross-check: run a BLS search (e.g., `astropy.timeseries.BoxLeastSquares`) over the same broad range. If BLS best period disagrees with the TLS alias-resolved period by more than 1 percent, re-apply the alias checkpoint using combined evidence; if they still disagree, prefer the period that passes the odd/even checkpoint. If both pass, prefer the longer period.
- Refine: narrow TLS search to +/- 2 to 5 percent around the final period for precision. Record `period_uncertainty`.
- Finalize: only emit the final period after both the alias and odd/even checkpoints pass. If either fails after one retry, emit the longer-period candidate and record a warning that disambiguation is unresolved.

## Constraints / Pitfalls
- Always pass `flux_err` to TLS; without it, SDE and depth uncertainties are unreliable and alias comparisons become meaningless.
- Never report the TLS top-SDE period without executing the alias and odd/even checkpoints; the half-period alias is the dominant failure mode in gapped or activity-dominated light curves.
- Do not pick a detrending window shorter than ~3x the expected transit duration; aggressive flattening suppresses the true transit and biases toward alias peaks.
- Do not treat TLS-vs-BLS disagreement as advisory; apply the deterministic tiebreaker (odd/even passes, then longer period).
- Do not hard-code period ranges, thresholds, or windows beyond the rules above; derive them from the data baseline, cadence, and candidate duration each run.
- Scope is single-signal recovery; do not expand into multi-planet masking, plotting, or method comparison unless explicitly required by the task.