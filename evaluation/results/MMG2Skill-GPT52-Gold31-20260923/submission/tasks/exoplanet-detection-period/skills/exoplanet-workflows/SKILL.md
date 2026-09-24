---
name: exoplanet-workflows
description: End-to-end workflow for detecting a transiting exoplanet in a stellar-variability-dominated
  light curve, including final period selection rules to avoid half/double-period
  aliases.
---

## Steps
1. Load data and confirm column meanings (time system, normalized flux, quality flag convention, flux uncertainty).
2. Filter on quality flags (typically `flag == 0` for TESS-like exports) and remove NaNs/infs.
3. Remove outliers conservatively (sigma-clip), then detrend stellar variability with a method that preserves short transits (e.g., `lightkurve.flatten` with window length longer than the transit duration).
4. Run a transit-focused period search (TLS preferred; BLS acceptable) over a broad period range.
5. Identify top candidate periods and **always check common harmonics** (`P`, `2P`, sometimes `P/2`) using:
   - odd/even transit-depth consistency,
   - folded-transit shape clarity,
   - SNR/SDE (or BLS depth SNR).
6. Only after alias resolution, do a narrow, dense-grid refinement around the chosen period to reach the precision needed for reporting.
7. Write the final period to `/root/period.txt` as a single value in days rounded to 5 decimals.
## Expected Result
A reproducible pipeline that detrends stellar activity, detects the transit period, and **finalizes the orbital period after harmonic/odd-even validation**, producing correctly formatted output.
