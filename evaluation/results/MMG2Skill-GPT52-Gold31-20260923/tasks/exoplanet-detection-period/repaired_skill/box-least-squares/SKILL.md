---
name: box-least-squares
description: Run an Astropy Box Least Squares (BLS) search for transit-like signals
  and **resolve half/double-period aliases** before finalizing and refining the orbital
  period.
---

## Steps
1. Prepare arrays `time` (days), `flux`, and (ideally) `flux_err`; remove NaNs and pre-detrend the light curve (e.g., with `lightkurve.flatten`) so stellar variability doesn’t dominate.
2. Build the BLS model:
   - `model = BoxLeastSquares(time * u.day, flux, dy=flux_err)`
3. Do a **broad** BLS search over a sensible duration grid:
   - `durations = np.linspace(0.01, 0.3, N) * u.day`
   - `pg = model.autopower(durations, objective="likelihood")` (or `"snr"` if correlated noise dominates)
4. Collect the strongest candidates (not just the top one):
   - Sort indices by `pg.power` descending; take top `k` periods.
5. For each candidate period `P`, **explicitly test harmonics** before choosing a “true” period:
   - Evaluate `P` and `2P` (and optionally `P/2`) using `compute_stats(period, duration, transit_time)` with matching `(duration, t0)` from the periodogram peak.
   - Prefer the period that yields:
     - higher `stats["depth_snr"]` (or better objective), **and**
     - **odd/even consistency**: `abs(stats["depth_odd"] - stats["depth_even"])` small compared to `stats["depth_err"]`, **and**
     - a plausible `stats["transit_count"]` (not spuriously inflated by a half-period fold).
6. After selecting the alias-resolved period `P_true`, **refine around both `P_true` and its nearest harmonic** (if applicable) on a dense grid, then re-apply the same alias check:
   - Example: `periods = np.linspace(P_true*(1-0.002), P_true*(1+0.002), 20000) * u.day`
   - `pg_ref = model.power(periods, duration_best, objective="likelihood")`
   - If the refined peak lands near `P/2` or `2P`, repeat Step 5 and keep the physically consistent choice.
7. Phase-fold at the final period (and optionally at `P/2` and `2P`) as a sanity check that a single transit event repeats cleanly at the chosen period.
## Expected Result
A best-fit orbital period that is **not a harmonic/alias** (e.g., avoids incorrectly reporting `P/2` when odd/even statistics favor `2P`) and is ready to be written (rounded) to the required output file.
