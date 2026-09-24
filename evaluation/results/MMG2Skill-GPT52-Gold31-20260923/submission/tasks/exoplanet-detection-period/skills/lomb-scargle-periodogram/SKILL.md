---
name: lomb-scargle-periodogram
description: Use Lomb–Scargle (via Lightkurve) to characterize strong sinusoidal/quasi-sinusoidal
  variability (e.g., stellar rotation) that may need to be detrended before transit
  searches.
---

## Steps
1. Create a `lightkurve.LightCurve(time=..., flux=..., flux_err=...)` from filtered data.
2. Compute a periodogram over a rotation-relevant range:
   - `pg = lc.to_periodogram(minimum_period=..., maximum_period=...)`
3. Read off the dominant period: `pg.period_at_max_power`.
4. Use the LS model (`pg.model(...)`) to visualize/confirm the modulation; use this insight to pick an appropriate detrending window length or variability-removal approach.
## Expected Result
An estimated stellar-variability timescale (often rotation) that informs detrending choices prior to transit detection.
