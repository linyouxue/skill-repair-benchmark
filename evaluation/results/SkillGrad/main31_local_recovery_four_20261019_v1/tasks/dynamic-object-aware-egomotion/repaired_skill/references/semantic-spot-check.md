# Semantic spot-check for masks + motion labels

Use this after format/coverage checks pass but before you finalize deliverables, especially when the evaluator is hidden and can fail you on meaning.

## What to sample
Pick a small set of sampled indices (e.g., 5–10) including early/middle/late. If you already have intervals, sample near interval boundaries too.

## 1) Dynamic-mask semantics

### Diagnostics to compute (fast)
- `mask_frac = nnz / (H*W)` per sampled frame.
- Connected-component stats: count, top-1/top-3 component area fractions.
- Spatial concentration: fraction of mask pixels within a border band (often indicates warp fill/parallax residuals).

```python
import numpy as np
import cv2

def mask_metrics(mask_bool):
    H, W = mask_bool.shape
    nnz = int(mask_bool.sum())
    frac = nnz / float(H * W)
    m = (mask_bool.astype(np.uint8) * 255)
    n, cc, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA] if n > 1 else np.array([], dtype=np.int64)
    areas = np.sort(areas)[::-1]
    top = (areas[:3] / float(H * W)).tolist() if areas.size else []

    b = max(2, min(H, W) // 20)  # ~5% border band
    border = np.zeros((H, W), bool)
    border[:b, :] = True; border[-b:, :] = True; border[:, :b] = True; border[:, -b:] = True
    border_frac = float(mask_bool[border].sum()) / (nnz + 1e-9)
    return {"mask_frac": frac, "cc_count": int(areas.size), "top_area_fracs": top, "border_frac": border_frac}

# Branch: too much foreground suggests global residuals
m = mask_metrics(mask_bool)
if m["mask_frac"] > 0.15 or m["border_frac"] > 0.5:
    print("FAIL(mask semantics): suspicious global/border residuals", m)
else:
    print("OK(mask semantics):", m)
```

### Optional qualitative overlay (recommended)
Overlay the mask on the RGB frame and save a few PNGs.

```python
def overlay(frame_bgr, mask_bool, color=(0, 0, 255), alpha=0.5):
    out = frame_bgr.copy()
    out[mask_bool] = (alpha * np.array(color) + (1 - alpha) * out[mask_bool]).astype(np.uint8)
    return out

# cv2.imwrite("debug_mask_i.png", overlay(frame_bgr, mask_bool))
```

## 2) Egomotion label semantics

### Warp-residual sanity check
For each sampled transition, check that your chosen global motion (affine/homography) actually stabilizes the frame.

```python
import numpy as np
import cv2

def mean_abs_diff(a, b, valid=None):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    if valid is None:
        return float(np.mean(d))
    v = d[valid]
    return float(np.mean(v)) if v.size else float("inf")

# Inputs: prev_gray, curr_gray, and a warp function producing warped_prev and valid
before = mean_abs_diff(curr_gray, prev_gray)
after = mean_abs_diff(curr_gray, warped_prev, valid)

if not (after < before):
    print("FAIL(motion model): warp did not reduce residual", {"before": before, "after": after})
else:
    print("OK(motion model):", {"before": before, "after": after})
```

### Runtime branch: label flicker / implausible combos
If labels change too often or co-occur implausibly, treat it as a sign your thresholds/model are wrong.

```python
# labels_per_sample: list[list[str]]
changes = sum(labels_per_sample[i] != labels_per_sample[i-1] for i in range(1, len(labels_per_sample)))
if changes / max(1, len(labels_per_sample)-1) > 0.5:
    print("FAIL(labels): excessive flicker → increase smoothing or thresholds")
else:
    print("OK(labels): flicker rate", changes)
```

## Verification + corrective action

If mask checks fail:
- Move from raw warp-difference thresholding to **dominant-motion outlier detection** (e.g., compute LK flow, fit a global model with RANSAC, mark outlier tracks, then rasterize), and/or tighten validity masking around borders.

If egomotion checks fail:
- If warp does not reduce residual: improve global model (homography, better features) or fallback to conservative labels.
- If warp reduces residual but directions seem inverted: run `egomotion-estimation/references/motion-sign-convention-check.md` and flip the mapping rule or invert the transform, then re-check on the same samples.

Always re-run this spot-check on the same sampled indices after changes before writing final outputs.
