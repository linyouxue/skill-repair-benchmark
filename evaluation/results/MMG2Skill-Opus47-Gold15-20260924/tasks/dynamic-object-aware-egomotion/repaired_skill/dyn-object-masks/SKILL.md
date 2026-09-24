---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation, output CSR sparse format."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.
# Workflow
1) **Dense flow**: compute Farneback dense optical flow between consecutive sampled gray frames.
2) **Robust global flow model**: fit a 2D affine flow model (u,v as linear in x,y) with IRLS + Tukey biweight so nearby-parallax pixels do not dominate; residual = observed flow − model flow.
3) **Residual thresholding**: threshold on residual magnitude using `max(min_px, median + k*MAD)` (e.g. `min_px≈3`, `k≈3`). Do NOT use raw absdiff — it produced 12–22% false-positive coverage.
4) **Morphology + area filter**: open then close; keep connected components above a minimum area (small enough to preserve pedestrians — e.g. ≥0.05% of image area, not a fixed large floor that suppresses small movers).
5) **Frame 0 handling**: no previous frame → emit an empty mask for the first sampled index (still write valid CSR arrays of size 0).
6) **CSR encoding**: for final bool mask
   - `rows, cols = nonzero(mask)`
   - `indices = cols.astype(int32)`; `data = ones(nnz, uint8)`
   - `counts = bincount(rows, minlength=H)`; `indptr = cumsum(counts, prepend=0).astype(int32)`
   - store as `f_{i}_data/indices/indptr`; also store `shape=[H,W]` int32.
# Sanity check on mask coverage
- If almost every frame is 0% in a busy street scene, thresholds are too strict — lower `min_px` or `min_area`.
- If any frame exceeds ~10% coverage, parallax on near objects is leaking through — increase IRLS iterations, widen the Tukey c, or raise `min_area`.
# Code sketch
```python
flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None,
                                    0.5, 3, 21, 3, 7, 1.5, 0)
# IRLS affine fit on (u,v) ~ [1,x,y]; then residual = flow - model_flow
res = np.linalg.norm(flow - model_flow, axis=2)
med = np.median(res); mad = 1.4826*np.median(np.abs(res-med))
thr = max(3.0, med + 3*mad)
raw = res > thr
m = cv2.morphologyEx(raw.astype(np.uint8)*255, cv2.MORPH_OPEN, k3)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k7)
n, cc, stats, _ = cv2.connectedComponentsWithStats(m>0, connectivity=8)
mask = np.zeros_like(raw, dtype=bool)
min_area = max(200, int(0.0005*H*W))
for cid in range(1,n):
    if stats[cid, cv2.CC_STAT_AREA] >= min_area:
        mask |= (cc==cid)
```
# Self-check
- [ ] Masks only for sampled frames; keys match sampled indices.
- [ ] `shape` stored as `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`.
- [ ] Residuals computed against a robust parallax-tolerant model, not raw absdiff.
- [ ] Per-frame coverage plausible for scene content (not uniformly 0% in obviously dynamic scenes).
