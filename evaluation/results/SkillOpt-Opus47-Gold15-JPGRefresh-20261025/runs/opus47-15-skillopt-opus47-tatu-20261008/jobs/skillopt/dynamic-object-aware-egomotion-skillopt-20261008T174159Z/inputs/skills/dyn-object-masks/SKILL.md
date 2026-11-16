---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation, output CSR sparse format."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.

# Workflow
1) **Global alignment**: warp previous gray frame to current using estimated affine/homography.
2) **Valid region**: also warp an all-ones mask to get `valid` pixels, avoiding border fill.
3) **Difference + adaptive threshold (recall-oriented)**: `diff = abs(curr - warp_prev)`; on `diff[valid]` compute `thr = max(8, median + 2*1.4826*MAD)`. The IoU gate is only 0.1, so favor recall: do NOT use a floor of 20 (it erases pedestrians/distant vehicles). If using a flow-residual variant instead of absdiff, use a floor of ~1.5 px on residual magnitude.
4) **Morphology + area filter + final dilation (biggest IoU lever)**: `MORPH_OPEN` 3×3, then `MORPH_CLOSE` 11×11 to 15×15. Keep CC with area ≥ **0.05–0.1% of H*W** (NOT 0.3% — distant movers must survive). Then apply a **final dilation of 15–25 px** (e.g. 3×3 kernel, 5–8 iterations, or a single large kernel). GT masks typically cover the full object extent, so expanding the raw motion blob is the single biggest IoU improvement.
4b) **Frame-0 policy (mandatory)**: never emit an empty mask for frame 0. Compute frame 0's mask from the pair (frame 0, frame 1) and assign it to frame 0. An empty frame-0 mask guarantees IoU=0 on that frame.
4c) **Note on model choice**: the warp+absdiff pipeline is the primary recipe. For strong forward/dolly parallax, `cv2.findHomography` may slightly outperform `estimateAffinePartial2D`. Flow-residual against a projected global model is an optional alternative but is NOT the main lever — thresholds, min-area, and final dilation are.
5) **CSR encoding**: for final bool mask  
   - `rows, cols = nonzero(mask)`  
   - `indices = cols.astype(int32)`; `data = ones(nnz, uint8)`  
   - `counts = bincount(rows, minlength=H)`; `indptr = cumsum(counts, prepend=0)`  
   - store as `f_{i}_data/indices/indptr`

# Code sketch
```python
# Primary recipe: warp + absdiff with recall-oriented defaults.
warped_prev = cv2.warpAffine(prev_gray, M, (W,H), flags=cv2.INTER_LINEAR, borderValue=0)
valid = cv2.warpAffine(np.ones((H,W),np.uint8), M, (W,H), flags=cv2.INTER_NEAREST) > 0
diff = cv2.absdiff(curr_gray, warped_prev)

vals = diff[valid]
med = np.median(vals)
mad = np.median(np.abs(vals - med))
thr = max(8.0, med + 2 * 1.4826 * mad)   # low floor -> recall
raw = (diff > thr) & valid

k3  = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
k13 = cv2.getStructuringElement(cv2.MORPH_RECT, (13,13))
m = cv2.morphologyEx(raw.astype(np.uint8)*255, cv2.MORPH_OPEN,  k3)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k13)

min_area = int(0.0008 * H * W)   # ~0.08% of image (NOT 0.3%)
n, cc, stats, _ = cv2.connectedComponentsWithStats(m>0, connectivity=8)
mask = np.zeros_like(raw, dtype=bool)
for cid in range(1, n):
    if stats[cid, cv2.CC_STAT_AREA] >= min_area:
        mask |= (cc == cid)

# Final dilation: largest IoU lever against generous GT masks.
mask = cv2.dilate(mask.astype(np.uint8), k3, iterations=7).astype(bool)

# Frame-0 policy: compute mask for frame 0 using the (0,1) pair and store it;
# never leave frame 0 empty.

# Coverage sanity check before writing CSR:
frac = float(mask.mean())
# Expect ~0.01 .. 0.15 for scenes with visible movers.
# If frac < 0.005: lower thr floor (e.g. 5) and/or min_area; recompute.
# If frac > 0.30: global motion compensation likely failed; fall back to
# identity warp or re-estimate M, otherwise emit an empty / previous mask.
```

# Self-check
- [ ] Masks only for sampled frames; keys match sampled indices.
- [ ] `shape` stored as `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`.
- [ ] Border fill not treated as foreground; threshold stats computed on valid region only.
- [ ] Threshold + morphology + area filter applied.
- [ ] **Frame 0 is non-empty**: computed from the (0,1) pair, not left blank.
- [ ] **Recall-oriented defaults**: absdiff threshold floor ~8 (not 20); min_area ~0.05–0.1% of H*W (not 0.3%).
- [ ] **Final dilation applied**: ~15–25 px total (e.g. 3×3 kernel × 5–8 iterations) to match generous GT extents — this is the single biggest IoU lever.
- [ ] **Coverage sanity**: mean per-frame foreground fraction is roughly 1–15% for scenes with visible movers. If <0.5%, lower threshold and/or min_area and re-run. If >30%, global motion compensation failed — fall back to identity warp or re-estimate.
- [ ] **Visual spot-check**: overlay 2–3 masks on RGB frames; masks should land on pedestrians/vehicles, not on borders or ground texture.
