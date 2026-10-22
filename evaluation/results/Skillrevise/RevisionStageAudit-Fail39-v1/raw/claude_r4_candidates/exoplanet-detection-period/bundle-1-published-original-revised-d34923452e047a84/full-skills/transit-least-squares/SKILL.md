# Transit Least Squares Transit Period Pipeline

## Purpose
Provide a reusable, checkpoint-driven workflow for detecting the orbital period of a transiting exoplanet in a light curve using Transit Least Squares (TLS), with explicit alias resolution and detrending adequacy checks so the final reported period is not a half or double alias of the true value.

## When to Use
Use when the task is to measure the orbital period (or confirm the presence) of a transiting exoplanet from a time-series light curve, and TLS or an equivalent transit search is available. Do not use for general periodicity (rotation, pulsation, eclipsing binaries); use Lomb-Scargle or BLS variants instead.

## Procedure
- Discover inputs and cadence
- Load time, flux, flux_err. If flux_err is missing, estimate it from a running MAD of the flux and record that the estimate is synthetic.
- Compute median cadence dt and total baseline T. Set period_min = max(2*dt, 0.5 days) and period_max = T/3 unless the task specifies otherwise.
- Evidence: print n_points, dt, T, period_min, period_max.
- Quality mask and outlier removal
- Apply any provided quality flags.
- Remove outliers with a sigma clip (start sigma=5; only use sigma=3 if the light curve is already smooth).
- Evidence: print n_removed and ensure n_removed/n_points < 0.2; if larger, loosen sigma.
- Detrend
- Primary path: flatten with a window_length roughly 2-3 times the longest expected transit duration (compute from an assumed Rstar and period range; otherwise use a window near 0.5-1.0 day for Kepler-like cadence as a starting guess, then adapt in step 4).
- Evidence: produce flux_detrended and residual_std = std(flux_detrended).
- Detrend adequacy check (fallback branch)
- Compute ratio = residual_std / median(flux_err).
- If ratio > 3, the light curve is likely stellar-activity-dominated. Fallback in order until ratio <= 3 or options are exhausted: a. Increase flatten window_length by 2x. b. Replace flatten with a spline or Savitzky-Golay detrend with a window chosen from the dominant low-frequency timescale. c. If a Gaussian Process detrender is available, fit a quasi-periodic GP to the out-of-transit flux and divide.
- Evidence: print chosen detrender and final ratio.
- Initial TLS search
- Run TLS over [period_min, period_max] with flux_err supplied. Record SDE, best_period P1, T0, duration, depth.
- Reject if SDE < 6; otherwise continue.
- Alias resolution checkpoint (mandatory)
- Evaluate TLS power (or re-run narrow TLS) at 0.5*P1 and 2*P1. Record SDE_half, SDE_double.
- Compute r_double = SDE_double / SDE_P1 and r_half = SDE_half / SDE_P1.
- If r_double >= 0.9 or r_half >= 0.9, flag alias and go to step 7. Otherwise, candidate_period = P1 and go to step 8.
- Odd-even depth and transit-count test
- For each candidate in {0.5*P1, P1, 2*P1} with SDE above threshold, phase-fold the detrended flux at that period, identify individual transit events, and compute depth_odd and depth_even plus n_events.
- Decision rule:
- If at candidate C the odd and even depths agree to within 20 percent and n_events is at least 3, C is self-consistent.
- Among self-consistent candidates, prefer the longest period (true period is never shorter than aliases that fold two different transits onto each other).
- If at P1 the odd and even depths differ by more than 20 percent while at 2*P1 they agree, choose 2*P1.
- If none is self-consistent, choose the candidate with the highest SDE and record low confidence.
- Evidence: log depth_odd, depth_even, n_events for each candidate and the chosen period.
- Refinement
- Rerun TLS over [0.98 * candidate_period, 1.02 * candidate_period] with an increased oversampling_factor to tighten the period and its uncertainty.
- Evidence: print refined period and period_uncertainty.
- Final validation before writing output
- Phase-fold at the refined period and visually or numerically assert that the model transit sits inside the data minimum and that out-of-transit baseline is flat.
- Assert SDE >= 6 and depth > 3 * median(flux_err) / sqrt(n_in_transit). If not, mark as weak detection.
- Write the period to the required output location only after these assertions pass.

## Constraints / Pitfalls
- Never skip the alias resolution checkpoint, even when SDE at P1 is very high; TLS aliasing between P and 2P is the dominant failure mode of this task family.
- Do not hard-code period_min, period_max, sigma, or window_length; derive them from cadence, baseline, and residual diagnostics discovered in steps 1-4.
- Always pass flux_err to TLS; if it is estimated from the data, do not treat SNR as an absolute reliability measure.
- Do not report a period whose odd-even depth test fails without an explicit low-confidence flag.
- Keep the detrending fallback bounded to the three options in step 4; do not loop indefinitely on detrender choices.
- Do not use this skill for non-transit periodic signals; use BLS or Lomb-Scargle instead.