---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation, output CSR sparse format."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.


## Key parameters (starting points)
- Feature/RANSAC: ORB 2k–5k keypoints; RANSAC reproj thresh 2–4 px; min inliers 30 and/or inlier ratio ≥0.25.
- Valid erosion: 3–8 px (increase if warp borders trigger).
- Thresholding: `k` in `median + k*MAD` typically 3–6; `thr_min` 20–35 for 8-bit gray at 5fps.
- Morphology kernels: open 3×3, close 7×7–11×11 (scale with resolution).
- Temporal: EMA α 0.5–0.8 or majority vote over last 3 sampled frames.
# Workflow
1) **Global alignment (robust model selection)**:
   - Detect/track features (e.g., ORB+BF, or LK optical flow). Estimate both **affine** and **homography** with RANSAC.
   - Prefer **affine** for mostly planar/weak perspective motion; prefer **homography** when there is noticeable rotation/zoom or strong projective effects.
   - **Quality checks** (fail fast): require enough inliers (e.g., `>= 30` or `>= 0.25×matches`) and reasonable reprojection error; reject transforms with extreme scale/shear.
   - **Fallback behavior**: if homography fails quality checks, fall back to affine; if both fail, fall back to identity (and tighten thresholds to avoid flooding).

2) **Valid region + warp-border suppression**:
   - Warp an all-ones mask to get `valid` pixels; then **erode** `valid` by a small radius (e.g., 3–8 px) to remove unstable warp borders.
   - Optionally downweight parallax-prone areas by building a **residual/confidence map** (e.g., local median of `diff`, or flow-consistency) and suppress detections where residual is consistent with background motion.

3) **Photometric normalization before differencing**:
   - Normalize illumination/exposure: apply light blur (Gaussian/median) and optionally CLAHE on grayscale before warping/diff.
   - Use `diff = abs(curr_norm - warp_prev_norm)` computed only where `valid` is true.

4) **Adaptive thresholding (robust + percentile) with fps/image-size aware floors**:
   - Compute robust stats on `diff[valid]` (median + k×MAD) **and** a high percentile (e.g., P95/P97). Set `thr = max(thr_min, min(median+k*MAD, P97))`.
   - Choose `thr_min` based on noise/fps (5fps often has larger inter-frame change): start with 20–35 for 8-bit gray and tune; ensure a minimum that prevents global triggering.

5) **Temporal stabilization to reduce flicker (5fps-friendly)**:
   - Smooth `diff` or masks across adjacent sampled frames: EMA on `diff` (`diff_ema = α*diff + (1-α)*prev_ema`, α≈0.5–0.8) then threshold.
   - Or apply **persistence filtering**: keep pixels/components that appear in ≥2 of the last 3 sampled masks (majority vote) to suppress one-frame flashes.

6) **Stronger morphology + connected-component filtering**:
   - Use open→close plus optional **hole filling**.
   - Filter components by **area ratio** and optional **shape/solidity** (remove thin border-like ribbons and tiny speckle). Optionally remove components touching the eroded `valid` border.

7) **Boundary refinement (improve Boundary IoU)**:
   - Refine edges via distance-transform based shrink/expand (e.g., slight erode then guided dilate), or intersect with image edges/gradient magnitude to avoid bleeding.

8) **CSR encoding**: for final bool mask  
   - `rows, cols = nonzero(mask)`  
   - `indices = cols.astype(int32)`; `data = ones(nnz, uint8)`  
   - `counts = bincount(rows, minlength=H)`; `indptr = cumsum(counts, prepend=0)`  
   - store as `f_{i}_data/indices/indptr`

# Code sketch
```python
def norm_gray(g):
    g = cv2.GaussianBlur(g, (5,5), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    return clahe.apply(g)

# 1) estimate transform with RANSAC; try H then affine (or vice versa) with inlier checks
# (pseudo) M, model = estimate_best_transform(prev_gray, curr_gray)

if model == 'H':
    warped_prev = cv2.warpPerspective(norm_gray(prev_gray), M, (W,H), flags=cv2.INTER_LINEAR, borderValue=0)
    valid = cv2.warpPerspective(np.ones((H,W),np.uint8), M, (W,H), flags=cv2.INTER_NEAREST) > 0
else:
    warped_prev = cv2.warpAffine(norm_gray(prev_gray), M, (W,H), flags=cv2.INTER_LINEAR, borderValue=0)
    valid = cv2.warpAffine(np.ones((H,W),np.uint8), M, (W,H), flags=cv2.INTER_NEAREST) > 0

# 2) suppress unstable borders
valid = cv2.erode(valid.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7))) > 0

# 3) diff + optional EMA temporal smoothing (keep state per stream)
diff = cv2.absdiff(norm_gray(curr_gray), warped_prev)
# diff_ema = alpha*diff + (1-alpha)*prev_diff_ema

vals = diff[valid]
med = np.median(vals)
mad = 1.4826*np.median(np.abs(vals - med))
p97 = np.percentile(vals, 97)
thr = max(thr_min, min(med + k*mad, p97))
raw = (diff > thr) & valid

# 4) morphology + hole fill + CC filtering
m = cv2.morphologyEx(raw.astype(np.uint8)*255, cv2.MORPH_OPEN, k3)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k7)
# optional: fill holes
m_flood = m.copy()
cv2.floodFill(m_flood, np.zeros((H+2,W+2),np.uint8), (0,0), 255)
m = m | cv2.bitwise_not(m_flood)

n, cc, stats, _ = cv2.connectedComponentsWithStats(m>0, connectivity=8)
mask = np.zeros((H,W), dtype=bool)
for cid in range(1, n):
    area = stats[cid, cv2.CC_STAT_AREA]
    if area < min_area:  # consider min_area as max(fraction*H*W, pixels)
        continue
    comp = (cc == cid)
    # optional: drop border-touching comps
    if np.any(comp & ~valid):
        continue
    mask |= comp

# 5) temporal persistence (example): mask = majority(mask_t, mask_t-1, mask_t-2)
```

# Self-check
- [ ] Masks only for sampled frames; keys match sampled indices.
- [ ] `shape` stored as `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`.
- [ ] Alignment quality checked: inliers/error within bounds; fallback (H→affine→identity) works.
- [ ] Border fill not treated as foreground: `valid` computed via warped ones-mask **and eroded**; optional rule removes components touching invalid/border.
- [ ] Photometric normalization applied before differencing.
- [ ] Threshold is robust (MAD/percentile) with explicit `thr_min` tuned for 5fps.
- [ ] Temporal stabilization enabled (EMA/majority vote/persistence) to reduce flicker.
- [ ] Morphology + hole fill + CC filtering (area ratio + optional solidity/shape) applied.
- [ ] Heuristics sanity checks before export:
  - sparsity: if mask coverage > X% (e.g., 30–50%) likely bad alignment → raise thr or use fallback transform
  - border activation: if many pixels near border are active → erode valid more or drop border-touching comps
  - flicker: if XOR mean between consecutive masks too high → increase persistence/EMA.
