---
name: exoplanet-workflows
description: General workflows and best practices for exoplanet detection and characterization from light curve data. Use when planning an exoplanet analysis pipeline, understanding when to use different methods, or troubleshooting detection issues.
---

# Exoplanet Detection Workflows

This skill provides general guidance on exoplanet detection workflows, helping you choose the right approach for your data and goals.

## Overview

Exoplanet detection from light curves typically involves:
1. Data loading and quality control
2. Preprocessing to remove instrumental and stellar noise
3. Period search using appropriate algorithms
4. Signal validation and characterization
5. Parameter estimation

## Pipeline Design Principles

### Key Stages

1. **Data Loading**: Understand your data format, columns, time system
2. **Quality Control**: Filter bad data points using quality flags
3. **Preprocessing**: Remove noise while preserving planetary signals
4. **Period Search**: Choose appropriate algorithm for signal type
5. **Validation**: Verify candidate is real, not artifact
6. **Refinement**: Improve period precision if candidate is strong

### Critical Decisions

**What to preprocess?**
- Remove outliers? Yes, but not too aggressively
- Remove trends? Yes, stellar rotation masks transits
- How much? Balance noise removal vs. signal preservation

**Which period search algorithm?**
- **TLS**: Best for transit-shaped signals (box-like dips)
- **Lomb-Scargle**: Good for any periodic signal, fast exploration
- **BLS**: Alternative to TLS, built into Astropy

**What period range to search?**
- Consider target star type and expected planet types
- Hot Jupiters: short periods (0.5-10 days)
- Habitable zone: longer periods (depends on star)
- Balance: wider range = more complete, but slower

**When to refine?**
- After finding promising candidate
- Narrow search around candidate period
- Improves precision for final measurement

## Choosing the Right Method

### Transit Least Squares (TLS)
**Use when:**
- Searching for transiting exoplanets
- Signal has transit-like shape (box-shaped dips)
- You have flux uncertainties

**Advantages:**
- Most sensitive for transits
- Handles grazing transits
- Provides transit parameters

**Disadvantages:**
- Slower than Lomb-Scargle
- Only detects transits (not RV planets, eclipsing binaries with non-box shapes)

### Lomb-Scargle Periodogram
**Use when:**
- Exploring data for any periodic signal
- Detecting stellar rotation
- Finding pulsation periods
- Quick period search

**Advantages:**
- Fast
- Works for any periodic signal
- Good for initial exploration

**Disadvantages:**
- Less sensitive to shallow transits
- May confuse harmonics with true period

### Box Least Squares (BLS)
**Use when:**
- Alternative to TLS for transits
- Available in astropy

**Note**: TLS generally performs better than BLS for exoplanet detection.

## Signal Validation

### Strong Candidate (TLS)
- **SDE > 9**: Very strong candidate
- **SDE > 6**: Strong candidate
- **SNR > 7**: Reliable signal

### Warning Signs
- **Low SDE (<6)**: Weak signal, may be false positive
- **Period exactly half/double expected**: Check for aliasing
- **High odd-even mismatch**: May not be planetary transit

### How to Validate

- **Signal strength metrics**: Check SDE, SNR against thresholds
- **Visual inspection**: Phase-fold data at candidate period
- **Odd-even consistency**: Do odd and even transits have same depth?
- **Multiple transits**: More transits = more confidence

## Multi-Planet Systems

Some systems have multiple transiting planets. Strategy:

1. Find first candidate
2. Mask out first planet's transits
3. Search remaining data for additional periods
4. Repeat until no more significant signals

See Transit Least Squares documentation for `transit_mask` function.

## Common Issues and Solutions

### Issue: No significant detection (low SDE)
**Solutions:**
- Check preprocessing - may be removing signal
- Try less aggressive outlier removal
- Check for data gaps during transits
- Signal may be too shallow for detection

### Issue: Period is 2x or 0.5x expected
**Causes:**
- Period aliasing from data gaps
- Missing alternate transits

**Solutions:**
- Check both periods manually
- Look at phase-folded light curves
- Check if one shows odd-even mismatch

### Issue: flux_err required error
**Solution:**
TLS requires flux uncertainties as the third argument - they're not optional!

### Issue: Results vary with preprocessing
**Diagnosis:**
- Compare results with different preprocessing
- Plot each preprocessing step
- Ensure you're not over-smoothing

## Expected Transit Depths

For context:
- **Hot Jupiters**: 0.01-0.03 (1-3% dip)
- **Super-Earths**: 0.001-0.003 (0.1-0.3% dip)
- **Earth-sized**: 0.0001-0.001 (0.01-0.1% dip)

Detection difficulty increases dramatically for smaller planets.

## Period Range Guidelines

Based on target characteristics:
- **Hot Jupiters**: 0.5-10 days
- **Warm planets**: 10-100 days
- **Habitable zone**:
  - Sun-like star: 200-400 days
  - M-dwarf: 10-50 days

Adjust search ranges based on mission duration and expected planet types.

## Best Practices

1. **Always include flux uncertainties** - critical for proper weighting
2. **Visualize each preprocessing step** - ensure you're improving data quality
3. **Check quality flags** - verify convention (flag=0 may mean good OR bad)
4. **Use appropriate sigma** - 3 for initial outliers, 5 after flattening
5. **Refine promising candidates** - narrow period search for precision
6. **Validate detections** - check SDE, SNR, phase-folded plots
7. **Consider data gaps** - may cause period aliasing
8. **Document your workflow** - reproducibility is key

## References

### Official Documentation
- [Lightkurve Tutorials](https://lightkurve.github.io/lightkurve/tutorials/index.html)
- [TLS GitHub](https://github.com/hippke/tls)
- [TLS Tutorials](https://github.com/hippke/tls/tree/master/tutorials)

### Key Papers
- Hippke & Heller (2019) - Transit Least Squares paper
- Kovács et al. (2002) - BLS algorithm

### Lightkurve Tutorial Sections
- Section 3.1: Identifying transiting exoplanet signals
- Section 2.3: Removing instrumental noise
- Section 3.2: Creating periodograms

## Dependencies

```bash
pip install lightkurve transitleastsquares numpy matplotlib scipy
```



## Validated Workflow for the Activity-Dominated Four-Column TESS Task

For `/root/data/tess_lc.txt`, interpret the four whitespace-separated columns as MJD time, normalized flux, quality flag, and flux uncertainty. Load all columns together, discard rows with non-finite values, retain only rows with `quality == 0`, and require finite positive uncertainties. Sort by time and apply every subsequent row mask identically to time, flux, and uncertainty; never independently filter or reorder the uncertainty column. Record the median cadence, the distribution of time gaps, and the total baseline before choosing search limits. Large gaps or separate observing segments should be treated explicitly when estimating trends and transit coverage.

Remove isolated instrumental outliers conservatively, using a robust residual criterion that does not clip coherent multi-point dips. Estimate and remove smooth stellar variability with a robust spline, rolling median, or low-order baseline whose timescale is substantially longer than a plausible transit duration. Iteratively mask candidate transit-like points while fitting the baseline, or otherwise use a transit-preserving detrend; do not smooth the raw flux with a scale short enough to absorb transits. Normalize the detrended flux consistently and propagate the aligned uncertainties through the normalization. Repeat the analysis with several reasonable detrending timescales rather than trusting one preprocessing choice.

Use Transit Least Squares (TLS) as the primary search on the cleaned, detrended arrays, passing the uncertainty array. Set the period interval from the measured cadence and baseline: exclude periods implausibly short for the sampling, and keep the upper bound low enough that a credible candidate produces multiple separated observed events. Search a duration grid resolved by the cadence and spanning physically plausible transit durations rather than using one arbitrary duration. Use Box Least Squares (BLS) on the same arrays as a cross-check, with uncertainties and a compatible period range. Refine promising TLS/BLS peaks on a denser local period grid.

Treat the strongest periodogram peak only as a candidate. For each leading candidate, inspect the signal-to-noise/significance, fitted depth and duration, number and locations of distinct events, and the phase-folded detrended light curve and residuals. Reject a candidate caused by smooth stellar activity or its harmonic, a cadence/window-function sampling alias, an implausibly short or long duration, or only one observed event. Explicitly compare `P`, `P/2`, `2P`, and other prominent aliases; the accepted period should give repeated transit-shaped events with coherent timing and depth. Check odd and even events separately for depth and morphology; a strong odd/even mismatch is evidence for an eclipsing binary or a half-period alias, not a validated planetary period. Require reasonable agreement between TLS and BLS and persistence of the candidate period, event locations, and morphology across the alternative detrending choices.

After validation, write only the orbital period in days to `/root/period.txt`, with no label or explanatory text and exactly five digits after the decimal point, for example:

```python
with open('/root/period.txt', 'w', encoding='ascii') as f:
    f.write(f'{validated_period:.5f}\n')
```
