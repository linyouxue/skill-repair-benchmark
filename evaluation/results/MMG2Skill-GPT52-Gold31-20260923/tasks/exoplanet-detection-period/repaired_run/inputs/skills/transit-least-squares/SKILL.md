---
name: transit-least-squares
description: Detect transiting exoplanets using Transit Least Squares (TLS) and validate
  against common period aliases (especially 2×/0.5×) before final reporting.
---

## Steps
1. Preprocess: quality-filter → outlier removal → detrend/flatten (preserve transit shapes).
2. Run TLS **with flux uncertainties**:
   - `pg = transitleastsquares(t, y, yerr)`
   - `res = pg.power(period_min=..., period_max=..., show_progress_bar=False, verbose=False)`
3. Record the candidate period and metrics (e.g., `res.period`, `res.SDE`, `res.snr`, `res.T0`, `res.duration`).
4. If TLS warnings or diagnostics suggest aliasing (or if a strong harmonic is plausible), compare `P` vs `2P` (and optionally `P/2`) by re-running TLS in a narrow window around each and/or comparing folded transits:
   - Prefer the period with cleaner, consistent transit events and better detection metrics.
5. Refine period precision by re-running TLS with a narrower period window around the selected (alias-resolved) period.
## Expected Result
A TLS-derived orbital period that has been checked against common harmonics (notably `2P`) so the reported value reflects the true orbit rather than an alias.
