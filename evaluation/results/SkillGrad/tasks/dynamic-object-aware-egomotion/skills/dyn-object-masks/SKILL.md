---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation and store them as per-frame CSR triplets."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.

# Workflow
1) **Global alignment**: warp previous gray frame to current using estimated affine/homography.
2) **Valid region**: warp an all-ones mask to get `valid` pixels, avoiding border fill.
3) **Difference + adaptive threshold**: compute `diff = abs(curr - warp_prev)`; on `diff[valid]` compute a robust threshold (median + k×MAD) with a minimum floor.
4) **Morphology + area filter**: open then close; keep connected components above a minimum area.
5) **CSR encoding**: for final boolean mask store per-frame triplets named by the true frame index: `f_{frame_id}_data/indices/indptr`.

# Code sketch
```python
import numpy as np, cv2

warped_prev = cv2.warpAffine(prev_gray, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
valid = cv2.warpAffine(np.ones((H, W), np.uint8), M, (W, H), flags=cv2.INTER_NEAREST) > 0

diff = cv2.absdiff(curr_gray, warped_prev)
vals = diff[valid]
med = np.median(vals)
mad = np.median(np.abs(vals - med))
thr = max(min_thr, med + k * 1.4826 * mad)
raw = (diff > thr) & valid

rows, cols = np.nonzero(raw)
order = np.argsort(rows, kind="stable")
rows, cols = rows[order], cols[order]
indices = cols.astype(np.int32)
data = np.ones(indices.size, dtype=np.uint8)
counts = np.bincount(rows, minlength=H).astype(np.int32)
indptr = np.concatenate(([0], np.cumsum(counts))).astype(np.int32)
```

# Self-check
- [ ] Keys use true frame ids (`f_{frame_id}_*`), not a 0..K counter.
- [ ] `shape` stored separately as `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`.
- [ ] Threshold stats computed on the valid region only.
