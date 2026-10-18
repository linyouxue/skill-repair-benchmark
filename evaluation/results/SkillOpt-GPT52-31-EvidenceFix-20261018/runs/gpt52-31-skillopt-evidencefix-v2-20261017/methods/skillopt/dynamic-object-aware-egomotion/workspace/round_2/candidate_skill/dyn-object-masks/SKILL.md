---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation, output CSR sparse format."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.


## Practical defaults (720p, 5fps sampling)
- **Alignment**: RANSAC reproj thresh 2–4 px; require inliers `>= 30` and inlier ratio `>= 0.25`.
- **Valid erosion**: 5–9 px (suppress warp borders).
- **Diff threshold**: `thr = max(thr_min, min(med + k*MAD, P97))` with `k=4–6`, `thr_min=25–40` (8-bit gray).
- **Morphology**: open 3×3; close 9×9 to 13×13 (increase if speckle).
- **Component filter**: `min_area = max(120, 0.0002*H*W)`; reject border-touching components.
- **Temporal**: 2-of-3 majority vote over masks (or EMA on diff with α=0.6–0.8).
# Workflow
1) **Estimate global transform with quality gates** (affine or homography):
   - Use feature matches (ORB) or tracked points (LK) and fit with RANSAC.
   - Record: inlier count, inlier ratio, and reprojection error.
   - **Accept only if** inliers and error pass thresholds (see defaults above). Reject extreme/degenerate transforms (near-singular, absurd scale/shear).
   - **Fallback**: if homography fails → try affine; if affine fails → identity (and tighten detection to avoid flooding).

2) **Warp + valid-region suppression**:
   - Warp `prev_gray` to current: `warp_prev`.
   - Warp an all-ones mask to get `valid`.
   - **Erode `valid`** (5–9 px at 720p) to suppress unstable warp borders.

3) **Optional photometric normalization (reduces illumination sensitivity)**:
   - Apply a light blur (3–5 px) and optionally CLAHE to `prev_gray` and `curr_gray` before warping/diff.
   - Use normalized differencing if needed: `diff = abs(curr_norm - warp_prev_norm)`.

4) **Robust thresholding (5fps-friendly)**:
   - Compute robust stats on `vals = diff[valid]`:
     - `med = median(vals)`
     - `MAD = 1.4826*median(|vals-med|)`
     - `P97 = percentile(vals, 97)`
   - Set threshold: `thr = max(thr_min, min(med + k*MAD, P97))`.
   - This limits triggers from parallax/warp residuals while keeping sensitivity to true movers.

5) **Morphology + connected-component filtering (reduce false positives)**:
   - `raw = (diff > thr) & valid`.
   - Apply open→close; optionally fill small holes.
   - Filter components by:
     - **area** (scale with image size)
     - **border-touch**: reject components that touch `~valid` (common warp artifact)
     - optional: reject thin ribbon-like components (high perimeter/area) if borders persist.

6) **Temporal stabilization (reduce flicker)**:
   - Maintain a short history on sampled frames.
   - Use **2-of-3 majority vote** on binary masks (or EMA on `diff` then threshold).
   - If using majority vote, still enforce `valid` each frame.

7) **CSR encoding**: for final bool mask  
   - `rows, cols = nonzero(mask)`  
   - `indices = cols.astype(int32)`; `data = ones(nnz, uint8)`  
   - `counts = bincount(rows, minlength=H)`; `indptr = cumsum(counts, prepend=0)`  
   - store as `f_{i}_data/indices/indptr`

# Code sketch
```python
warped_prev = cv2.warpAffine(prev_gray, M, (W,H), flags=cv2.INTER_LINEAR, borderValue=0)
valid = cv2.warpAffine(np.ones((H,W),uint8), M, (W,H), flags=cv2.INTER_NEAREST)>0
diff = cv2.absdiff(curr_gray, warped_prev)
vals = diff[valid]
thr = max(20, np.median(vals) + 3*1.4826*np.median(np.abs(vals - np.median(vals))))
raw = (diff>thr) & valid
m = cv2.morphologyEx(raw.astype(uint8)*255, cv2.MORPH_OPEN, k3)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k7)
n, cc, stats, _ = cv2.connectedComponentsWithStats(m>0, connectivity=8)
mask = np.zeros_like(raw, dtype=bool)
for cid in range(1,n):
    if stats[cid, cv2.CC_STAT_AREA] >= min_area:
        mask |= (cc==cid)
```

# Self-check
- [ ] Masks only for sampled frames; keys match sampled indices.
- [ ] `shape` stored as `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`.
- [ ] **Transform QA**: RANSAC inliers/ratio/error checked; fallback (H→affine→identity) implemented.
- [ ] **Border suppression**: `valid` computed via warped ones-mask **and eroded**; border-touching components rejected.
- [ ] Threshold stats computed on `diff[valid]` only; threshold uses MAD + percentile cap + `thr_min` tuned for 5fps.
- [ ] Temporal stabilization enabled (2-of-3 vote or EMA) to reduce flicker.
- [ ] Quick heuristics (debug/tuning):
  - If `mask.mean()` is consistently huge (e.g., >0.30) → alignment failed or `thr_min` too low; increase erosion/threshold or force fallback.
  - If adjacent-frame XOR flicker is high (e.g., >0.10) → increase temporal smoothing / tighten transform QA.
  - If activations cluster near borders → erode `valid` more and/or strengthen border-touch rejection.
