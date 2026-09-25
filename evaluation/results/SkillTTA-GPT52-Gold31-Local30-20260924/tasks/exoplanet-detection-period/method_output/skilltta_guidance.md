# SKILL.md

## When to use
Use this skill when you must extract an exoplanet orbital period from a space-telescope light curve where stellar variability (rotational modulation, oscillations, spots) dominates and hides shallow transit signals. The contract typically requires:
- Reading a provided light-curve file with time, flux, quality flags, and uncertainties.
- Filtering bad-quality data and outliers.
- Detrending/removing stellar variability without erasing transit features.
- Estimating the planet’s orbital period and writing it as a single number (days) with specified rounding to an output file.

Before acting, gather evidence from the dataset:
- Column meanings and units (confirm time unit is in days; confirm flux is normalized).
- Fraction of points with good quality flags and presence of NaNs/infs.
- Cadence/typical sampling and data gaps (affects period search grid).
- Approximate timescale of stellar variability vs expected transit duration (guides detrending window).

## Possible Failure Modes
- **Using bad data**: ignoring quality flags or misunderstanding which value indicates “good,” leaving artifacts that create false periodicities.
- **Over-aggressive outlier removal**: sigma-clipping or masking that accidentally removes transits (transits can look like “negative outliers”).
- **Over-detrending**: choosing a smoothing window too short, or a model too flexible, which fits away transit dips and suppresses the periodic signal.
- **Under-detrending**: leaving strong stellar modulation, causing the periodogram to lock onto stellar rotation harmonics rather than the transit period.
- **Time-base mistakes**: assuming time is in a different unit (hours vs days), not accounting for uneven sampling, or using index-based spacing.
- **Period-search pitfalls**: inadequate frequency grid, ignoring aliases (e.g., 1-day sampling artifacts), selecting harmonic (P/2, 2P) rather than fundamental.
- **Not validating the candidate**: reporting the top periodogram peak without phase-fold inspection and consistency checks across data segments.
- **Output-format errors**: writing extra text/newlines, wrong rounding precision, or wrong file path.

## Possible procedures
1. **Load and basic sanitation**
   - Read the file into arrays: time, flux, quality, flux_err.
   - Keep only finite values; drop NaNs/infs.
   - Filter by quality flag to retain “good” points per contract.
   - (Decision point) If many gaps exist, keep them (do not interpolate over large gaps for transit searches); prefer methods robust to irregular sampling.

2. **Outlier handling (transit-safe)**
   - Use robust statistics (median/MAD) rather than mean/std.
   - Prefer **asymmetric** clipping (more tolerant of downward excursions) to avoid removing transits.
   - Alternatively: clip only extreme positive outliers and very deep isolated negatives inconsistent with transit duration/cadence.

3. **Detrend stellar variability while preserving transits**
   - Estimate the variability timescale via a quick smoothing/periodogram on the raw flux (aim only to learn the scale).
   - Choose a detrending approach:
     - **Running median / biweight filter** with window **significantly longer** than expected transit duration (often hours) but shorter than long-term drifts.
     - **Savitzky–Golay** or **spline** fit with knot spacing longer than transit features.
     - **Harmonic/low-frequency model** (Fourier series) if variability is quasi-sinusoidal.
     - **Gaussian Process** (quasi-periodic kernel) if needed, but ensure it does not absorb transits (mask candidate transits or constrain kernel).
   - Compute detrended flux as `flux / trend` (or `flux - trend`, consistent with normalization).
   - (Recovery check) If detrended series shows flattened transits (no sharp dips), increase smoothing window / reduce model flexibility.

4. **Search for transit period**
   - Use a transit-optimized period search such as **Box Least Squares (BLS)** on detrended flux.
   - Define a reasonable period range:
     - Lower bound: a few cadences to avoid ultra-short artifacts.
     - Upper bound: a fraction of total time baseline (need multiple transits for confidence).
   - Include a grid for transit durations consistent with cadence and plausible transit lengths.
   - Evaluate candidates by BLS power/SNR and the consistency of transit depth/shape.

5. **Resolve aliases and harmonics**
   - Check whether the strongest period is a harmonic:
     - Fold at P, 2P, and P/2 and compare whether transits align into a single consistent event per orbit.
   - Inspect peaks near common alias spacings; prefer the period that yields:
     - Sharper, repeatable transit dips at consistent phase.
     - Comparable depth and duration across multiple events.
   - (Decision point) If multiple peaks compete, split the light curve into halves and confirm the period appears in both.

6. **Finalize and write output**
   - Select the period in **days**.
   - Round to the required decimal places.
   - Write exactly one numeric value to the required output file path (no labels, no extra formatting).

## Verification Checklist
- [ ] Input file read correctly; columns mapped to time/flux/quality/uncertainty as specified.
- [ ] Quality filtering applied using the contract’s definition of “good” data.
- [ ] Outlier treatment did not systematically remove downward dips (transit-safe check).
- [ ] Detrending method preserves short-duration features; trend window/model is longer/smoother than transit timescales.
- [ ] Period search method is transit-appropriate (e.g., BLS) and uses a sufficiently dense period grid for the dataset baseline and cadence.
- [ ] Candidate period validated by phase-folded light curve showing repeated transit-like dips at a consistent phase.
- [ ] Harmonic/alias check performed (compare folding at P, 2P, P/2; ensure correct fundamental).
- [ ] Output file contains **only** the numeric period in days, rounded exactly to the required precision, with no extra text.
- [ ] No concrete details copied from retrieved examples; all decisions are based on the current task’s data and contract.
- [ ] If any step produced ambiguous evidence (multiple peaks, weak SNR), rerun with adjusted detrending window and/or period grid and re-validate by folding.
