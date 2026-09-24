---
name: light-curve-preprocessing
description: Clean and detrend a TESS-like light curve (quality filtering, outlier
  removal, flattening) while preserving transit signals.
---

## Steps
1. Load the columns: time (MJD), normalized flux, quality flag, flux uncertainty.
2. Apply quality filtering first (commonly `quality == 0` for good data); drop NaNs/infs.
3. Remove gross outliers (sigma clipping); use a conservative threshold if transits are shallow (e.g., `sigma≈5–10`).
4. Detrend stellar/instrumental variability with `lightkurve.LightCurve.flatten(window_length=...)`:
   - Choose `window_length` long compared to transit duration but short enough to remove rotation/spot modulation.
5. Optionally run a second outlier removal pass on the detrended light curve (often slightly tighter than the first).
6. Inspect before/after plots to ensure transits are not over-smoothed or removed.
## Expected Result
A cleaned, detrended light curve where stellar activity is largely removed and transit-like dips are preserved for TLS/BLS searches.
