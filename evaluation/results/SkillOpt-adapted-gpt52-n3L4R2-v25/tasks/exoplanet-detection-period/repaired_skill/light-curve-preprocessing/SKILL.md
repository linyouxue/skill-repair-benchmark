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

A fixed `window_length` is not generally safe because its physical timescale depends on cadence and transit duration. Estimate the cadence from sorted time differences and choose several baseline timescales that are comfortably longer than plausible transit durations; test the result rather than assuming that a particular number of cadences preserves transits. Prefer a robust rolling baseline, spline, or comparable low-frequency model, and divide (or subtract, consistently) the flux by that baseline. Fit the baseline after masking candidate negative dips, or iteratively refit: make an initial robust baseline, identify candidate transit windows, exclude those windows from the baseline fit, and refit. This prevents shallow repeated transits from being absorbed into the activity model.

Transform uncertainties with the same operations. For multiplicative flattening, `flux_flat = flux / baseline` and `error_flat = flux_err / abs(baseline)`; renormalizing by a scalar requires dividing both arrays by that scalar. Do not use a smoothing scale so short that it follows transit ingress/egress or so long that strong stellar oscillations remain. Compare multiple physically plausible scales and retain only transit-like signals that persist while low-frequency residual power decreases.

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

Parse and validate the columns together. For the standard TESS convention, quality flag `0` means usable data, so retain `flag == 0`; do not invert this rule merely because the alternative looks visually cleaner. Remove rows with nonfinite MJD, flux, flag, or uncertainty, and require finite strictly positive uncertainties. Validate that the time values are in MJD days, sort all columns by time, and remove duplicate or non-increasing timestamps if the downstream method requires strictly increasing time. Every mask, gap split, normalization, and detrending operation must be applied to the uncertainty array as well as the flux array.

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



## Reproducible Activity-Dominated Transit Preprocessing

For a four-column TESS text file containing MJD, normalized flux, quality flag, and flux uncertainty, use this order: load and validate exactly four numeric columns; retain finite rows with `quality == 0` and `flux_err > 0`; sort by MJD; and apply any isolated-outlier mask to all columns. Estimate the cadence from robust central time differences and identify gaps substantially larger than the cadence. Treat separated segments independently when a gap or sector boundary makes a single baseline inappropriate, normalizing each segment by a robust median while scaling its uncertainty by the same factor.

Estimate stellar activity with a robust low-frequency model such as a spline or rolling median/LOWESS. Its physical timescale must be longer than plausible transit durations, and it should be evaluated at several scales rather than selected from cadence alone. Before fitting, mask provisional negative transit-like points; then refit the activity baseline and repeat once or twice. Alternatively, use iterative sigma-clipped robust fitting that clips only baseline residuals and does not discard coherent, repeated dips. Divide flux and uncertainty by the fitted baseline for multiplicative flattening. Preserve the original time and row mapping so candidate events can be inspected in the unflattened data.

Run the transit search on each detrending variant with the corresponding uncertainty array. Compare residual low-frequency power or RMS before and after detrending, and compare the candidate's search significance, depth, duration, number of distinct events, and phase-folded morphology across baseline timescales. A useful preprocessing choice reduces the oscillatory residuals without erasing repeated transit-shaped dips; a peak that appears only for one aggressive window, or disappears when candidate dips are masked during baseline fitting, is not robust. Save or plot the masks, segment boundaries, baselines, uncertainties, and residual light curves for verification.
