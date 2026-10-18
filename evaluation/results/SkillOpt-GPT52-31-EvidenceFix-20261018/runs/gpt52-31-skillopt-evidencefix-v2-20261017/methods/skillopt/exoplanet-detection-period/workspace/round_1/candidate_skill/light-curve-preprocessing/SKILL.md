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

## Outlier Removal

### Using Lightkurve

```python
import lightkurve as lk

# Remove outliers using sigma clipping
lc_clean, mask = lc.remove_outliers(sigma=3, return_mask=True)
outliers = lc[mask]  # Points that were removed

# Common sigma values:
# sigma=3: Standard (removes ~0.3% of data)
# sigma=5: Conservative (removes fewer points)
# sigma=2: Aggressive (removes more points)
```

### Manual Outlier Removal

```python
import numpy as np

# Calculate median and standard deviation
median = np.median(flux)
std = np.std(flux)

# Remove points beyond 3 sigma
good = np.abs(flux - median) < 3 * std
time_clean = time[good]
flux_clean = flux[good]
error_clean = error[good]
```

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

The `flatten()` method uses a Savitzky–Golay-like filter to remove trends, but it only preserves transit signals if the **window_length is chosen conservatively** (much longer than the transit duration). Too-short windows or overly flexible trend models can distort transit shapes and introduce short-period artifacts.

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

### Important Principles

- **Always include flux_err**: Critical for proper weighting in period search algorithms
- **Preserve transit shapes**: Use methods like `flatten()` that preserve short-duration dips
- **Don't over-process**: Too aggressive preprocessing can remove real signals
- **Verify visually**: Plot each step to ensure quality

### Parameter Selection

- **Outlier removal sigma**: Lower sigma (2-3) is aggressive, higher (5-7) is conservative
- **Flattening window**: Should be longer than transit duration but shorter than stellar rotation period
- **When to do two passes**: Remove obvious outliers before detrending, then remove residual outliers after



- **Estimate variability period(s) first**: Use a coarse Lomb–Scargle/ACF on the raw-cleaned flux to get \(P_{\mathrm{var}}\); then set detrending windows relative to \(P_{\mathrm{var}}\) (avoid windows comparable to \(P_{\mathrm{var}}\) that can leave residual structure).
- **Iterative transit masking**: For variable stars, plan on: detrend → BLS/TLS → mask transits → re-detrend → re-run BLS/TLS to avoid biasing the trend fit and to reduce harmonic confusion.
## Preprocessing for Exoplanet Detection

For transit detection, be careful not to remove the transit signal:

1. **Remove outliers first**: Use sigma=3 or sigma=5
2. **Flatten trends**: Use window_length appropriate for your data
3. **Don't over-process**: Too much smoothing can remove shallow transits



### Detrending recipe for transit searches in variable stars (TESS)

When stellar variability dominates (rotation/spot modulation, pulsations), detrending choices strongly affect BLS/TLS. A common failure mode is **over-aggressive detrending** creating short-period structure that pushes BLS toward **harmonics** of the true orbital period.

**Recommended workflow (iterative transit masking):**

1. **Estimate variability timescales before detrending**
   - Compute a coarse periodogram (e.g., Lomb–Scargle) on the cleaned flux to identify the dominant variability period(s) (rotation/pulsation). Use this only to set detrending scales, not as the planet period.

2. **Choose a flattening window using physical timescales**
   - Let \(T_{\mathrm{dur}}\) be an expected transit duration guess (typical TESS planets are hours: \(\sim 0.05\)–\(0.3\) d).
   - Pick a flattening/smoothing window \(W\) such that:
     - **\(W \gg T_{\mathrm{dur}}\)** (rule of thumb: \(W \ge 5\)–\(10\,T_{\mathrm{dur}}\)) to preserve transit shape.
     - **\(W \ll P_{\mathrm{var}}\)** where possible (e.g., \(W \lesssim 0.2\)–\(0.5\,P_{\mathrm{var}}\)) so variability is removed without fitting out transits.
   - If variability is multi-periodic or evolving, prefer **piecewise** detrending (per sector/orbit or with breakpoints) instead of one global high-order fit.

3. **Initial detrend → search → mask → re-detrend → re-search**
   - (a) Detrend/flatten once and run BLS/TLS.
   - (b) Phase-fold on the best candidate period and **mask in-transit points** (use the candidate epoch + duration, and pad the mask slightly).
   - (c) Re-run flattening **on the masked light curve** (or fit the trend on masked data and apply it to the unmasked flux).
   - (d) Re-run BLS/TLS on the re-flattened series. Iterate until the candidate period stabilizes.

4. **Harmonic sanity checks**
   - Explicitly inspect peaks at \(P\), \(2P\), \(P/2\), \(3P\), etc. Strong stellar variability + imperfect detrending often makes \(P/2\) or \(P/3\) appear stronger than \(P\).
   - Compare folded transit shapes at the top few periods: the true period should give consistent transit depth/shape and no odd/even mismatch.

**Warnings (what not to do):**
- Avoid very short windows or high-order polynomials/splines that can **fit into transits**, distort depths, and inject artificial short-period ripples.
- Iterative sine fitting can accidentally remove or reshape transit signals if the fitted frequency (or its aliases) overlaps the transit comb; if used, combine with **transit masking** and keep iterations minimal.
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
