---
name: transit-least-squares
description: Transit Least Squares (TLS) for detecting periodic transit-shaped dips in light curves.
---

# Transit Least Squares (TLS)

TLS is optimized for transit-shaped signals and is often more sensitive than BLS for shallow transits.

## Minimal usage

```python
import transitleastsquares as tls

tls_model = tls.transitleastsquares(time, flux, flux_err)
out = tls_model.power(period_min=p_min, period_max=p_max, show_progress_bar=False)
period = out.period
```

## Harmonics / aliasing (P vs 2P)

If TLS shows multiple strong solutions at harmonically related periods (near **P and 2P**, or warns that the true period may be twice the given period), do not pick purely by SDE.

Decision rule:
- Treat **odd/even consistency and phase-fold coverage** as primary for transits when harmonics exist; prefer the candidate that produces consistent events, even if its SDE is slightly lower.

Read references/period-alias-disambiguation.md when TLS (or a companion BLS run) yields competing peaks near P and 2P (or P/2).
Skip when the best period is isolated and the phase-folded transit is clearly single-peaked with consistent depths.

## Common pitfalls

- Reporting a half-period alias because it has the highest SDE while 2P is more physically consistent.
- Omitting `flux_err` (TLS expects uncertainties for proper weighting).
