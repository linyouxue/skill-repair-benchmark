---
name: light-curve-preprocessing
description: Preprocessing and cleaning techniques for astronomical light curves. Use when preparing light curve data for period analysis, including outlier removal, trend removal, flattening, and handling data quality flags. Works with lightkurve and general time series data.
---

# Light Curve Preprocessing

Preprocessing is essential before period analysis. Raw light curves often contain outliers, long-term trends, and instrumental effects that can mask or create false periodic signals.

## Overview

Common preprocessing steps:
1. Remove outliers
2. Remove long-term trends
3. Handle data quality flags
4. Remove stellar variability (optional)



### Transit-preserving principle (critical for period searches)
When your goal is **transit detection**, detrending must remove variability on timescales **much longer** than the expected transit duration, otherwise you can create/strengthen short-period aliases.

- Choose detrending/flattening windows **~5–20× the expected transit duration** (and preferably longer if stellar rotation is strong).
- Avoid methods/parameters that can fit away short dips (overfitting) or that introduce ringing near sharp features.
- Prefer **segment-wise detrending** when there are gaps/discontinuities (e.g., between TESS orbits/sectors) so the filter does not bridge gaps.
## Outlier Removal

**Caution (transits can look like outliers):** sigma-clipping on the **raw flux** can remove real in-transit points, biasing BLS/Lomb–Scargle results. Prefer clipping on **detrended residuals**, and/or use asymmetric clipping that targets only positive excursions (flares).

### Using Lightkurve (recommended pattern)

```python
import lightkurve as lk

# 0) Apply quality flags first (see next section)

# 1) Light detrend/flatten (transit-preserving window; see guidance below)
lc_flat = lc.flatten(window_length=500)

# 2) Sigma-clip on residuals (lc / lc_flat) rather than raw flux
resid = lc / lc_flat
resid_clean, mask = resid.remove_outliers(sigma=5, return_mask=True)

# Apply the same mask back to original series
lc_clean = lc[~mask]
```

### Manual approach (clip residuals, not raw flux)

```python
import numpy as np

# Given a detrended baseline model 'trend' (e.g., from smoothing)
resid = flux / trend
med = np.median(resid)
mad = np.median(np.abs(resid - med))
robust_sigma = 1.4826 * mad

# Conservative clipping to avoid removing transits
good = np.abs(resid - med) < 5 * robust_sigma

time_clean = time[good]
flux_clean = flux[good]
error_clean = error[good]
```

**Do not treat in-transit points as outliers.** If you see clusters of negative residuals at a consistent phase, mask them as candidate transits (see iterative workflow below) rather than clipping them away.

## Removing Long-Term Trends

### Flattening with Lightkurve

```python
# Flatten to remove low-frequency variability
# window_length: number of cadences to use for smoothing
lc_flat = lc_clean.flatten(window_length=500)

# Common window lengths:
# 100-200: Remove short-term trends
# 300-500: Remove medium-term trends (typical for TESS)
# 500-1000: Remove long-term trends
```

The `flatten()` method uses a Savitzky-Golay filter to remove trends while preserving transit signals.



#### Choosing `window_length` to preserve transits
`window_length` is in **cadences**, so convert an expected transit duration (hours) into cadences for your data cadence.

- Rule of thumb for transit searches: set the smoothing window to **5–20× transit duration**.
- If `window_length` is too short, the filter will partially remove the dip and can push period searches toward **short aliases**.

If cadence is 2 min, then 1 hour ≈ 30 cadences; a 3-hour transit is ≈ 90 cadences, so a safe starting window might be 500–2000 cadences (depending on variability strength).

#### Gaps and discontinuities
For light curves with gaps or jumps, do **piecewise normalization/detrending** (e.g., by orbit/sector or by contiguous time segments) and then stitch the normalized segments. Avoid smoothing across large gaps.
### Iterative Sine Fitting

For removing high-frequency stellar variability (rotation, pulsation):

```python
def sine_fitting(lc):
    """Remove dominant periodic signal by fitting sine wave."""
    pg = lc.to_periodogram()
    model = pg.model(time=lc.time, frequency=pg.frequency_at_max_power)
    lc_new = lc.copy()
    lc_new.flux = lc_new.flux / model.flux
    return lc_new, model

# Iterate multiple times to remove multiple periodic components
lc_processed = lc_clean.copy()
for i in range(50):  # Number of iterations
    lc_processed, model = sine_fitting(lc_processed)
```

**Warning**: This removes periodic signals, so use carefully if you're searching for periodic transits.

## Handling Data Quality Flags

**IMPORTANT**: Quality flag conventions vary by data source!

### Standard TESS format
```python
# For standard TESS files (flag=0 is GOOD):
good = flag == 0
time_clean = time[good]
flux_clean = flux[good]
error_clean = error[good]
```

### Alternative formats
```python
# For some exported files (flag=0 is BAD):
good = flag != 0
time_clean = time[good]
flux_clean = flux[good]
error_clean = error[good]
```

**Always verify your data format!** Check which approach gives cleaner results.

## Preprocessing Pipeline Considerations

When building a preprocessing pipeline for exoplanet detection:

### Key Steps (Order Matters!)

1. **Quality filtering**: Apply data quality flags first
2. **Outlier removal**: Remove bad data points (flares, cosmic rays)
3. **Trend removal**: Remove long-term variations (stellar rotation, instrumental drift)
4. **Optional second pass**: Additional outlier removal after detrending



### Iterative workflow to prevent variability leakage into the periodogram
A robust transit-search loop is:

1. **Quality flags → initial detrend/flatten** (window ≫ transit duration)
2. **Initial search (e.g., BLS)** to get a candidate period
3. **Mask in-transit cadences** using the candidate ephemeris (and a generous duration window)
4. **Re-detrend using only out-of-transit points** (reduces the filter being pulled down by transits)
5. **Re-run the search** and compare aliases (check for peaks at P, 1/2 P, 2P)

Require **before/after plots** at each major step (raw, detrended, masked detrend) to verify:
- transits are not flattened away
- detrending removed rotational variability without introducing short-timescale structure
- no systematic over-clipping of negative dips
### Important Principles

- **Always include flux_err**: Critical for proper weighting in period search algorithms
- **Preserve transit shapes**: Use methods like `flatten()` that preserve short-duration dips
- **Don't over-process**: Too aggressive preprocessing can remove real signals
- **Verify visually**: Plot each step to ensure quality

### Parameter Selection

- **Outlier removal sigma**: Lower sigma (2-3) is aggressive, higher (5-7) is conservative
- **Flattening window**: Should be longer than transit duration but shorter than stellar rotation period
- **When to do two passes**: Remove obvious outliers before detrending, then remove residual outliers after

## Preprocessing for Exoplanet Detection

For transit detection, be careful not to remove the transit signal:

1. **Remove outliers first**: Use sigma=3 or sigma=5
2. **Flatten trends**: Use window_length appropriate for your data
3. **Don't over-process**: Too much smoothing can remove shallow transits

## Visualizing Results

Always plot your light curve to verify preprocessing quality:

```python
import matplotlib.pyplot as plt

# Use .plot() method on LightCurve objects
lc.plot()
plt.show()
```

**Best practice**: Plot before and after each major step to ensure you're improving data quality, not removing real signals.

## Dependencies

```bash
pip install lightkurve numpy matplotlib
```

## References

- [Lightkurve Preprocessing Tutorials](https://lightkurve.github.io/lightkurve/tutorials/index.html)
- [Removing Instrumental Noise](https://lightkurve.github.io/lightkurve/tutorials/2.3-removing-noise.html)

## Best Practices

1. **Always check quality flags first**: Remove bad data before processing
2. **Remove outliers before flattening**: Outliers can affect trend removal
3. **Choose appropriate window length**: Too short = doesn't remove trends, too long = removes transits
4. **Visualize each step**: Make sure preprocessing improves the data
5. **Don't over-process**: More preprocessing isn't always better
