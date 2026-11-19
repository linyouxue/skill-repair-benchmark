---
name: transit-least-squares
description: Transit Least Squares (TLS) algorithm for detecting exoplanet transits in light curves. Use when searching for transiting exoplanets specifically, as TLS is more sensitive than Lomb-Scargle for transit-shaped signals. Based on the transitleastsquares Python package.
---

# Transit Least Squares (TLS)

Transit Least Squares is a specialized algorithm optimized for detecting exoplanet transits in light curves. It's more sensitive than Lomb-Scargle for transit-shaped signals because it fits actual transit models.

## Overview

TLS searches for periodic transit-like dips in brightness by fitting transit models at different periods, durations, and epochs. It's the preferred method for exoplanet transit detection.

## Installation

```bash
pip install transitleastsquares
```

## Basic Usage

**CRITICAL**: Always include `flux_err` (flux uncertainties) for best results!

```python
import transitleastsquares as tls
import lightkurve as lk
import numpy as np

# Example 1: Using Lightkurve (recommended)
lc = lk.LightCurve(time=time, flux=flux, flux_err=error)
lc_clean = lc.remove_outliers(sigma=3)
lc_flat = lc_clean.flatten()

# Create TLS object - MUST include flux_err!
pg_tls = tls.transitleastsquares(
    lc_flat.time.value,      # Time array
    lc_flat.flux.value,      # Flux array
    lc_flat.flux_err.value   # Flux uncertainties (REQUIRED!)
)

# Search for transits (uses default period range if not specified)
# Tip: start with a reasonable period range to keep runtime manageable.
out_tls = pg_tls.power(
    show_progress_bar=False,  # Set True for progress tracking
    verbose=False
)

# Extract results
best_period = out_tls.period
period_uncertainty = out_tls.period_uncertainty
t0 = out_tls.T0                    # Transit epoch
depth = out_tls.depth               # Transit depth
snr = out_tls.snr                   # Signal-to-noise ratio
sde = out_tls.SDE                   # Signal Detection Efficiency

print(f"Best period: {best_period:.5f} ± {period_uncertainty:.5f} days")
print(f"Transit epoch (T0): {t0:.5f}")
print(f"Depth: {depth:.5f}")
print(f"SNR: {snr:.2f}")
print(f"SDE: {sde:.2f}")
```

### Example 2: With explicit period range
```python
# Search a specific period range (recommended)
# Keeping the range realistic prevents very long runtimes.
out_tls = pg_tls.power(
    period_min=2.0,      # Minimum period (days)
    period_max=7.0,      # Maximum period (days)
    show_progress_bar=True,
    verbose=True
)
```

## Runtime & Robustness Tips

TLS can be compute-heavy on long light curves and wide period ranges.

Practical tips:
- **Start with a bounded period range** (e.g., 0.5–15 days for many TESS sectors) instead of the full default range.
- **Detrend first** and do a **second conservative outlier pass** after detrending.
- If a broad TLS run is slow or unstable, use **BLS** (Astropy/Lightkurve) to get a short list of candidate periods, then refine with TLS in narrow windows.

## Period Refinement Strategy

**Best Practice**: Broad search first, then refine for precision.

**Example workflow:**
1. Initial search finds candidate at ~3.2 days
2. Refine by searching narrower range (e.g., 3.0-3.4 days)
3. Narrower range → finer grid → better precision

**Why?** Initial searches use coarse grids (fast). Refinement uses dense grid in small range (precise).

```python
# After initial search finds a candidate, narrow the search:
results_refined = pg_tls.power(
    period_min=X,  # e.g., 90% of candidate
    period_max=Y   # e.g., 110% of candidate
)
```

**Typical refinement window**: ±2% to ±10% around candidate period.

### Advanced Options

For very precise measurements, you can adjust:
- `oversampling_factor`: Finer period grid (default: 1, higher = slower but more precise)
- `duration_grid_step`: Transit duration sampling (default: 1.1)
- `T0_fit_margin`: Mid-transit time fitting margin (default: 5)

### Advanced Parameters

- `oversampling_factor`: Higher values give finer period resolution (slower)
- `duration_grid_step`: Step size for transit duration grid (1.01 = 1% steps)
- `T0_fit_margin`: Margin for fitting transit epoch (0 = no margin, faster)

## Phase-Folding

Once you have a period, TLS automatically computes phase-folded data:

```python
# Phase-folded data is automatically computed
folded_phase = out_tls.folded_phase      # Phase (0-1)
folded_y = out_tls.folded_y              # Flux values
model_phase = out_tls.model_folded_phase # Model phase
model_flux = out_tls.model_folded_model # Model flux

# Plot phase-folded light curve
import matplotlib.pyplot as plt
plt.plot(folded_phase, folded_y, '.', label='Data')
plt.plot(model_phase, model_flux, '-', label='Model')
plt.xlabel('Phase')
plt.ylabel('Flux')
plt.legend()
plt.show()
```

## Transit Masking

After finding a transit, mask it to search for additional planets:

```python
from transitleastsquares import transit_mask

# Create transit mask
mask = transit_mask(time, period, duration, t0)
lc_masked = lc[~mask]  # Remove transit points

# Search for second planet
pg_tls2 = tls.transitleastsquares(
    lc_masked.time,
    lc_masked.flux,
    lc_masked.flux_err
)
out_tls2 = pg_tls2.power(period_min=2, period_max=7)
```

## Interpreting Results

### Signal Detection Efficiency (SDE)

SDE is TLS's measure of signal strength, but it depends on preprocessing (detrending, masking, window length), so treat thresholds as heuristics:
- **SDE > 9**: Very strong candidate
- **SDE > 6**: Promising candidate
- **SDE < 6**: Weak signal; validate carefully and try alternative detrending

### Signal-to-Noise Ratio (SNR)

- **SNR > 7**: Generally considered reliable
- **SNR < 7**: May need additional validation

### Common Warnings

TLS may warn: "X of Y transits without data. The true period may be twice the given period."

This suggests:
- Data gaps may cause period aliasing
- The algorithm may have returned **P/2**
- Check **P**, **P/2**, and **2P** explicitly using the *same detrended light curve*

#### Practical alias check (recommended)

Because transit searches can favor harmonics, add an explicit check after your broad search:

1. Let **P** be the best period from a broad TLS run.
2. Re-run TLS in *narrow windows* around **P**, **P/2**, and **2P** (e.g., ±2–5%) **using the same detrended light curve** and compare:
   - SDE/SNR
   - `odd_even_mismatch` (if available)
   - `depth_odd` vs `depth_even` (if available)
   - number of distinct transits / missing transits (if available)
3. Prefer the period with consistent odd/even depths and a clean single-transit-per-cycle folded light curve.

If odd/even depths differ strongly at **P**, it often indicates the true orbital period is **2P**.

Tip: if TLS is slow, you can do the alias check with **Astropy BLS** first (much faster) and then confirm the winner with a narrow-window TLS run.

## Model Light Curve

TLS provides the best-fit transit model:

```python
# Model over full time range
model_time = out_tls.model_lightcurve_time
model_flux = out_tls.model_lightcurve_model

# Plot with data
import matplotlib.pyplot as plt
plt.plot(time, flux, '.', label='Data')
plt.plot(model_time, model_flux, '-', label='Model')
plt.xlabel('Time [days]')
plt.ylabel('Flux')
plt.legend()
plt.show()
```

## Workflow Considerations

When designing a transit detection pipeline, consider:

1. **Data quality**: Filter by quality flags before analysis
2. **Preprocessing order**: Remove outliers → flatten/detrend → search for transits
3. **Initial search**: Use broad period range to find candidates
4. **Refinement**: Narrow search around candidates for better precision
5. **Validation**: Check SDE, SNR, and visual inspection of phase-folded data

### Typical Parameter Ranges

- **Outlier removal**: sigma=3-5 (lower = more aggressive)
- **Period search**: Match expected orbital periods for your target
- **Refinement window**: ±2-10% around candidate period
- **SDE threshold**: >6 for candidates, >9 for strong detections

## Multiple Planet Search Strategy

1. **Initial broad search**: Use TLS with default or wide period range
2. **Identify candidate**: Find period with highest SDE
3. **Refine period**: Narrow search around candidate period (±5%)
4. **Mask transits**: Remove data points during transits
5. **Search for additional planets**: Repeat TLS on masked data

## Dependencies

```bash
pip install transitleastsquares lightkurve numpy matplotlib
```

## References

- [TLS GitHub Repository](https://github.com/hippke/tls)
- [TLS Tutorials](https://github.com/hippke/tls/tree/master/tutorials)
- [Lightkurve Tutorials](https://lightkurve.github.io/lightkurve/tutorials/index.html)
- [Lightkurve Exoplanet Examples](https://lightkurve.github.io/lightkurve/tutorials/3.1-identifying-transiting-exoplanets.html)

## When to Use TLS vs. Lomb-Scargle

- **Use TLS**: When specifically searching for exoplanet transits
- **Use Lomb-Scargle**: For general periodic signals (rotation, pulsation, eclipsing binaries)

TLS is optimized for transit-shaped signals and is typically more sensitive for exoplanet detection.

## Common Issues

### "flux_err is required"
Always pass flux uncertainties to TLS! Without them, TLS cannot properly weight data points.

### Period is 2x or 0.5x expected
Check for period aliasing — the true period might be double or half of what TLS reports. Do **not** choose based on SDE/SNR alone:
- Compare **P**, **P/2**, and **2P** on the same detrended curve.
- Use odd/even depth consistency (`odd_even_mismatch`, `depth_odd`, `depth_even`) when available.
- Validate by phase-folding at each candidate period.

### Low SDE (<6)
- Signal may be too weak
- Try different preprocessing (less aggressive flattening)
- Check if there's a data gap during transits
