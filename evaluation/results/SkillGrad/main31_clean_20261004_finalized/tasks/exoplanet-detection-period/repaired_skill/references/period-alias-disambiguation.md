# Period alias disambiguation for transit searches (P vs 2P vs P/2)

Use this procedure when period searches (BLS/TLS/Lomb–Scargle) return competing strong candidates at harmonically related periods (near **P and 2P**, or sometimes **P/2**). In transit detection, the **fundamental orbital period** can be misidentified as a half-period alias when alternating events (odd/even) differ.

## Procedure

### 1) Build a harmonic candidate set

Start from the current best period `P0` and explicitly test its near harmonics.

```python
import numpy as np

P0 = float(best_period_days)
candidates = sorted({P0, 2*P0, 0.5*P0})
```

Runtime branch: if `0.5*P0` is outside your search bounds or produces <2 events, drop it.

### 2) Compute consistency diagnostics for each candidate

Prefer a transit-specific diagnostic when available.

#### Branch A: You have a BLS model (Astropy)

```python
import numpy as np

rows = []
for P in candidates:
    # pick nearest evaluated grid point
    j = int(np.argmin(np.abs(period_grid_days - P)))
    stats = bls.compute_stats(period_grid[j], duration_grid[j], t0_grid[j])

    odd_even_sigma = abs(stats["depth_odd"] - stats["depth_even"]) / stats["depth_err"]
    rows.append({
        "P": float(period_grid[j].to_value()),
        "power": float(power_grid[j]),
        "depth_snr": float(stats["depth_snr"]),
        "odd_even_sigma": float(odd_even_sigma),
        "ntr": int(stats["transit_count"]),
    })
```

#### Branch B: You have a TLS result (transitleastsquares)

TLS may not expose the same odd/even stats; lean more on phase-fold shape and “missing transits” warnings.

```python
rows = []
for P in candidates:
    out = tls_model.power(period_min=0.98*P, period_max=1.02*P, show_progress_bar=False)
    rows.append({"P": float(out.period), "SDE": float(out.SDE), "SNR": float(out.snr)})
```

Runtime branch: if TLS warns that many transits have no data, treat the reported `P` as suspect and ensure `2P` is in the candidate set.

### 3) Choose the fundamental period using a hierarchy

Decision rule:
1. **Reject half-period aliases:** if `odd_even_sigma(P)` is large (e.g., ≳ 3) but `odd_even_sigma(2P)` is small (≲ 1), choose **2P**.
2. If odd/even is similar across candidates, prefer the candidate with:
   - higher depth SNR (or TLS SNR/SDE), and
   - more observed events (`transit_count`) and better phase coverage.
3. If both look plausible, keep both as hypotheses and run a local refinement search around each.

## Verification step

After selecting `P*`, verify by re-folding and re-estimating consistency:

```python
# pseudo-checks; implement with your plotting/summary utilities
assert n_transits_at(P_star) >= 2, "too few events for a reliable period"
assert odd_even_sigma_at(P_star) <= odd_even_sigma_at(P_star/2), "alias not improved"
```

If verification fails:
- If `n_transits_at(P*)` is low: expand the time baseline (more sectors/quarters) or widen the period search.
- If odd/even mismatch remains high: treat as potential eclipsing binary or systematics; revisit detrending and run an alternative search method (TLS if BLS, or vice versa).
