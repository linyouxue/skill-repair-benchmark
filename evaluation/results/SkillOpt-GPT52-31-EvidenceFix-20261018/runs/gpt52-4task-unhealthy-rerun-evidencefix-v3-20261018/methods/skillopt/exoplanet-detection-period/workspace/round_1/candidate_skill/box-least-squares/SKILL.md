---
name: box-least-squares
description: Box Least Squares (BLS) periodogram for detecting transiting exoplanets and eclipsing binaries. Use when searching for periodic box-shaped dips in light curves. Alternative to Transit Least Squares, available in astropy.timeseries. Based on Kovács et al. (2002).
---

# Box Least Squares (BLS) Periodogram

The Box Least Squares (BLS) periodogram is a statistical tool for detecting transiting exoplanets and eclipsing binaries in photometric time series data. BLS models a transit as a periodic upside-down top hat (box shape) and finds the period, duration, depth, and reference time that best fit the data.

## Overview

BLS is built into Astropy and provides an alternative to Transit Least Squares (TLS). Both search for transits, but with different implementations and performance characteristics.

**Key parameters BLS searches for:**
- Period (orbital period)
- Duration (transit duration)
- Depth (how much flux drops during transit)
- Reference time (mid-transit time of first transit)

## Installation

BLS is part of Astropy:

```bash
pip install astropy
```

## Basic Usage

```python
import numpy as np
import astropy.units as u
from astropy.timeseries import BoxLeastSquares

# Prepare data
# time, flux, and flux_err should be numpy arrays or Quantities
t = time * u.day  # Add units if not already present
y = flux
dy = flux_err  # Optional but recommended

# Create BLS object
model = BoxLeastSquares(t, y, dy=dy)

# Automatic period search with specified duration
duration = 0.2 * u.day  # Expected transit duration
periodogram = model.autopower(duration)

# Extract results
best_period = periodogram.period[np.argmax(periodogram.power)]
print(f"Best period: {best_period:.5f}")
```

## Using autopower vs power

### autopower: Automatic Period Grid

Recommended for initial searches. Automatically determines appropriate period grid:

```python
# Specify duration (or multiple durations)
duration = 0.2 * u.day
periodogram = model.autopower(duration)

# Or search multiple durations
durations = [0.1, 0.15, 0.2, 0.25] * u.day
periodogram = model.autopower(durations)
```

### power: Custom Period Grid

For more control over the search:

```python
# Define custom period grid
periods = np.linspace(2.0, 10.0, 1000) * u.day
duration = 0.2 * u.day

periodogram = model.power(periods, duration)
```

**Warning**: Period grid quality matters! Too coarse and you'll miss the true period.

## Objective Functions

BLS supports two objective functions:

### 1. Log Likelihood (default)

Maximizes the statistical likelihood of the model fit:

```python
periodogram = model.autopower(0.2 * u.day, objective='likelihood')
```

### 2. Signal-to-Noise Ratio (SNR)

Uses the SNR with which the transit depth is measured:

```python
periodogram = model.autopower(0.2 * u.day, objective='snr')
```

The SNR objective can improve reliability in the presence of correlated noise.

## Complete Example

```python
import numpy as np
import matplotlib.pyplot as plt
import astropy.units as u
from astropy.timeseries import BoxLeastSquares

# Load and prepare data
data = np.loadtxt('light_curve.txt')
time = data[:, 0] * u.day
flux = data[:, 1]
flux_err = data[:, 3]

# Create BLS model
model = BoxLeastSquares(time, flux, dy=flux_err)

# Run BLS with automatic period grid
# Try multiple durations to find best fit
durations = np.linspace(0.05, 0.3, 10) * u.day
periodogram = model.autopower(durations, objective='likelihood')

# Find peak
max_power_idx = np.argmax(periodogram.power)
best_period = periodogram.period[max_power_idx]
best_duration = periodogram.duration[max_power_idx]
best_t0 = periodogram.transit_time[max_power_idx]
max_power = periodogram.power[max_power_idx]

print(f"Period: {best_period:.5f}")
print(f"Duration: {best_duration:.5f}")
print(f"T0: {best_t0:.5f}")
print(f"Power: {max_power:.2f}")

# Plot periodogram
import matplotlib.pyplot as plt
plt.plot(periodogram.period, periodogram.power)
plt.xlabel('Period [days]')
plt.ylabel('BLS Power')
plt.show()
```

## Peak Statistics for Validation

Use `compute_stats()` to calculate detailed statistics about a candidate transit:

```python
# Get statistics for the best period
stats = model.compute_stats(
    periodogram.period[max_power_idx],
    periodogram.duration[max_power_idx],
    periodogram.transit_time[max_power_idx]
)

# Key statistics for validation
print(f"Depth: {stats['depth']:.6f}")
print(f"Depth uncertainty: {stats['depth_err']:.6f}")
print(f"SNR: {stats['depth_snr']:.2f}")
print(f"Odd/Even mismatch: {stats['depth_odd'] - stats['depth_even']:.6f}")
print(f"Number of transits: {stats['transit_count']}")

# Check for false positives
if abs(stats['depth_odd'] - stats['depth_even']) > 3 * stats['depth_err']:
    print("Warning: Significant odd-even mismatch - may not be planetary")
```

**Validation criteria:**
- **High depth SNR (>7)**: Strong signal
- **Low odd-even mismatch**: Consistent transit depth
- **Multiple transits observed**: More reliable
- **Reasonable duration**: Not too long or too short for orbit

## Period Grid Sensitivity

The BLS periodogram is sensitive to period grid spacing. The `autoperiod()` method provides a conservative grid:

```python
# Get automatic period grid
periods = model.autoperiod(durations, minimum_period=1*u.day, maximum_period=10*u.day)
print(f"Period grid has {len(periods)} points")

# Use this grid with power()
periodogram = model.power(periods, durations)
```

**Tips:**
- Use `autopower()` for initial searches
- Use finer grids around promising candidates
- Period grid quality matters more for BLS than for Lomb-Scargle

## Comparing BLS Results

To compare multiple peaks:


### Validation & common failure modes (read before trusting the max peak)

**BLS often returns a highest-power peak that is *not* the true orbital period.** The top peak can be a **harmonic/subharmonic** (e.g., P/2, P/3, 2P, 3P) or a **window/cadence alias** caused by gaps, sampling, or detrending leakage—especially in TESS light curves with residual stellar variability.

**Do this validation checklist for each candidate period (at least the top N peaks):**
1. **Inspect top N peaks (not just argmax)** and keep the best few candidates for follow-up.
2. **Harmonic / subharmonic sweep:** explicitly evaluate **P, 2P, 3P, P/2, P/3** using the *same duration prior/grid* and compare objective values and folded coherence.
3. **Phase-fold + bin + model overlay:** confirm a coherent, repeatable **box-shaped dip** at the candidate period.
4. **Odd/even depth test + secondary eclipse check:** odd/even mismatch or a significant secondary at phase ~0.5 suggests an eclipsing binary or wrong period.
5. **Duration sanity:** reject solutions that require implausibly long durations for the period/star (see duration guidance below).
6. **Assess robustness:** if available, use `compute_stats()` SNR, try bootstrap/FAP-like checks, and verify the signal persists under reasonable detrending choices.

**Concrete harmonic test snippet (use on each top peak):**
```python
# Given a candidate period P0 (Quantity), evaluate common aliases/harmonics
candidates = [P0, 2*P0, 3*P0, P0/2, P0/3]
rows = []
for P in candidates:
    # Reuse the same durations you used in the period search
    pgP = model.power([P], durations, objective='likelihood')
    st = model.compute_stats(pgP.period[0], pgP.duration[0], pgP.transit_time[0])
    rows.append((P.to_value(u.day), float(pgP.power[0]), float(st['depth_snr']), int(st['transit_count'])))

# Sort by power (or depth_snr) and then *still* verify by folded plots
rows = sorted(rows, key=lambda r: r[1], reverse=True)
for r in rows:
    print(f"P={r[0]:.6f} d  power={r[1]:.2f}  depth_snr={r[2]:.2f}  Ntr={r[3]}")
```

**Example failure mode:** It is common for the maximum-power BLS peak to land near a shorter period (e.g., ~1.4 d) while the true planet period is longer (e.g., ~5.36 d) because the shorter period aligns dips from stellar variability residuals or matches a harmonic. Checking **2P, 3P** and inspecting the **folded, binned** transit shape typically reveals the correct longer period.
```python
# Find top 5 peaks
sorted_idx = np.argsort(periodogram.power)[::-1]
top_5 = sorted_idx[:5]

print("Top 5 candidates:")
for i, idx in enumerate(top_5):
    period = periodogram.period[idx]
    power = periodogram.power[idx]
    duration = periodogram.duration[idx]

    stats = model.compute_stats(period, duration, periodogram.transit_time[idx])

    print(f"\n{i+1}. Period: {period:.5f}")
    print(f"   Power: {power:.2f}")
    print(f"   Duration: {duration:.5f}")
    print(f"   SNR: {stats['depth_snr']:.2f}")
    print(f"   Transits: {stats['transit_count']}")
```

## Phase-Folded Light Curve

After finding a candidate, phase-fold to visualize the transit:


**Strong recommendation:** always **bin** the folded light curve and overlay a box model. Unbinned scatter can hide that the dip is not coherent.

```python
import numpy as np
import matplotlib.pyplot as plt

P = best_period
t0 = best_t0
phase = ((time - t0 + 0.5*P) % P) / P - 0.5  # center transit near 0

# Bin
nbin = 80
bins = np.linspace(-0.5, 0.5, nbin+1)
idx = np.digitize(phase.to_value(u.dimensionless_unscaled) if hasattr(phase,'to_value') else phase, bins) - 1
bin_x = 0.5*(bins[:-1] + bins[1:])
bin_y = np.array([np.nanmedian(flux[idx==k]) if np.any(idx==k) else np.nan for k in range(nbin)])

plt.figure(figsize=(7,4))
plt.plot(phase, flux, '.', ms=2, alpha=0.3)
plt.plot(bin_x, bin_y, '-', lw=2)
plt.xlabel('Phase')
plt.ylabel('Flux')
plt.title(f'Folded at P={P.to_value(u.day):.5f} d')
plt.show()
```

If the binned curve does **not** show a stable box-like dip near phase 0, treat the period as suspect and revisit other peaks/harmonics.
```python
# Fold the light curve at the best period
phase = ((time.value - best_t0.value) % best_period.value) / best_period.value

# Plot to verify transit shape
import matplotlib.pyplot as plt
plt.plot(phase, flux, '.')
plt.xlabel('Phase')
plt.ylabel('Flux')
plt.show()
```

## BLS vs Transit Least Squares (TLS)

Both methods search for transits, but differ in implementation:

### Box Least Squares (BLS)
**Pros:**
- Built into Astropy (no extra install)
- Fast for targeted searches
- Good statistical framework
- compute_stats() provides detailed validation

**Cons:**
- Simpler transit model (box shape)
- Requires careful period grid setup
- May be less sensitive to grazing transits

### Transit Least Squares (TLS)
**Pros:**
- More sophisticated transit models
- Generally more sensitive
- Better handles grazing transits
- Automatic period grid is more robust

**Cons:**
- Requires separate package
- Slower for very long time series
- Less control over transit shape

**Recommendation**: Try both! TLS is often more sensitive, but BLS is faster and built-in.

## Integration with Preprocessing

BLS works best with preprocessed data. Consider this pipeline:

1. **Quality filtering**: Remove flagged data points
2. **Outlier removal**: Clean obvious artifacts
3. **Detrending**: Remove stellar variability (rotation, trends)
4. **BLS search**: Run period search on cleaned data
5. **Validation**: Use `compute_stats()` to check candidate quality

### Key Considerations

- Preprocessing should **preserve transit shapes** (use gentle methods like `flatten()`)
- Don't over-process - too aggressive cleaning removes real signals
- BLS needs reasonable period and duration ranges
- Always validate with multiple metrics (power, SNR, odd-even)



### Duration sanity guidance (especially for TESS)
Overly permissive duration grids can inflate spurious BLS power. In most TESS planet cases, transit durations are **hours-scale**, not fractions of a day approaching half a day.

**Practical bounds (rule-of-thumb):**
- Start with durations spanning roughly **0.5–10 hours** (≈ 0.02–0.4 d) for many short-to-moderate periods.
- Avoid allowing durations that are a large fraction of the period (e.g., **duration >~ 0.2·P**) unless you have strong justification.
- If stellar parameters are available, tie bounds to geometry: transit duration scales with **P** and **stellar density**; very long durations at short periods are usually unphysical.

**Implementation tip:** use a duration grid that scales with period when doing follow-up `power()` calls around a candidate period, rather than a single very long fixed duration.
## Common Issues

### Issue: No clear peak
**Causes:**
- Transits too shallow
- Wrong duration range
- Period outside search range
- Over-aggressive preprocessing

**Solutions:**
- Try wider duration range
- Extend period search range
- Use less aggressive `flatten()` window
- Check raw data for transits

### Issue: Highest BLS peak is a harmonic/subharmonic (P/2, P/3, 2P, 3P) or an alias
**Causes:**
- True signal produces strong power at harmonics/subharmonics (common for box models)
- Residual stellar variability after detrending creates repeatable dips at shorter aliases
- Data gaps / window function and cadence artifacts
- Detrending leakage (overfitting trends can distort transit shape)

**Solutions (systematic, not ad hoc):**
- Review the **top N peaks**, then for each candidate explicitly test **P, 2P, 3P, P/2, P/3** with the **same duration grid**.
- Require a coherent **phase-folded + binned** transit shape with a model overlay.
- Use `compute_stats()` for **odd/even** depth comparison and check for a **secondary eclipse** near phase ~0.5.
- Prefer candidates with realistic **duration** and sufficient **transit_count**.

### Issue: High odd-even mismatch
**Cause:**
- Not a planetary transit
- Eclipsing binary
- Instrumental artifact

**Solution:**
- Check `stats['depth_odd']` vs `stats['depth_even']`
- May not be a transiting planet

## Dependencies

```bash
pip install astropy numpy matplotlib
# Optional: lightkurve for preprocessing
pip install lightkurve
```

## References

### Official Documentation
- [Astropy BLS Documentation](https://docs.astropy.org/en/stable/timeseries/bls.html)
- [Astropy Time Series Guide](https://docs.astropy.org/en/stable/timeseries/)

### Key Papers
- **Kovács, Zucker, & Mazeh (2002)**: Original BLS paper - [A&A 391, 369](https://arxiv.org/abs/astro-ph/0206099)
- **Hartman & Bakos (2016)**: VARTOOLS implementation - [A&C 17, 1](https://arxiv.org/abs/1605.06811)

### Related Resources
- [Lightkurve Tutorials](https://lightkurve.github.io/lightkurve/tutorials/)
- [TLS GitHub](https://github.com/hippke/tls) - Alternative transit detection method

## When to Use BLS

**Use BLS when:**
- You want a fast, built-in solution
- You need detailed validation statistics (`compute_stats`)
- Working within the Astropy ecosystem
- You want fine control over period grid

**Use TLS when:**
- Maximum sensitivity is critical
- Dealing with grazing or partial transits
- Want automatic robust period grid
- Prefer more sophisticated transit models

**Use Lomb-Scargle when:**
- Searching for general periodic signals (not specifically transits)
- Detecting stellar rotation, pulsation
- Initial exploration of periodicity

For exoplanet detection, both BLS and TLS are valid choices. Try both and compare results!
