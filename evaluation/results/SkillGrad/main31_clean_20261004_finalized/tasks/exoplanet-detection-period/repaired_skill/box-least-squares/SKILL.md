---
name: box-least-squares
description: Box Least Squares (BLS) periodogram for detecting transiting exoplanets and eclipsing binaries.
---

# Box Least Squares (BLS) Periodogram

The Box Least Squares (BLS) periodogram detects periodic box-shaped dips (transits/eclipses) in light curves.

## Quick workflow

1. Preprocess (quality filter → outliers → flatten/detrend).
2. Run a broad BLS search.
3. Compare top candidates with both **signal metrics** (power/SNR) and **consistency checks** (odd/even depth, phase coverage).
4. Refine around the selected period on a narrower grid.

## Basic usage

```python
import numpy as np
import astropy.units as u
from astropy.timeseries import BoxLeastSquares

bls = BoxLeastSquares(time * u.day, flux, dy=flux_err)
periodogram = bls.autopower(durations * u.day)
idx = np.argmax(periodogram.power)
period = periodogram.period[idx]
duration = periodogram.duration[idx]
t0 = periodogram.transit_time[idx]
```

## Comparing BLS results (avoid half/double-period aliases)

When strong candidates appear at **P and 2P (or P/2)**, raw BLS power can favor an alias.

Prefer the period that is **physically consistent for transits**, using odd/even depth consistency and phase-fold coverage.

```python
import numpy as np

# candidates should include likely harmonics of the top peak
candidates = [p1, p2]  # e.g., P and 2P as Quantity
rows = []
for p in candidates:
    j = int(np.argmin(np.abs(periodogram.period - p)))
    stats = bls.compute_stats(
        periodogram.period[j],
        periodogram.duration[j],
        periodogram.transit_time[j],
    )
    odd_even_sigma = abs(stats["depth_odd"] - stats["depth_even"]) / stats["depth_err"]
    rows.append((periodogram.period[j], periodogram.power[j], stats["depth_snr"], odd_even_sigma, stats["transit_count"]))
```

Decision rule (alias disambiguation):
- If a candidate at P has **significant odd/even mismatch** but 2P has **near-zero mismatch**, treat P as a **half-period alias** and choose 2P, even if P has slightly higher power.
- If both have similar odd/even consistency, prefer higher depth SNR and better phase-folded transit shape/coverage.

Read references/period-alias-disambiguation.md when the top candidates include harmonics (near P and 2P, or P/2) and the choice is ambiguous.
Skip when there is a single isolated peak and the phase-folded transit is unambiguous.

## Common pitfalls

- Picking the highest-power peak when harmonics are present; use odd/even depth consistency and phase-fold coverage to select the fundamental.
- Using an overly coarse period grid; refine around the chosen period.
- Over-aggressive detrending/outlier removal that suppresses transit depth.
