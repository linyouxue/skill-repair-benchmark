---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation, output CSR sparse format."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.

# Workflow
1) **Global alignment via homography**: estimate `H` with `cv2.findHomography(..., cv2.RANSAC)` from feature matches (ORB or goodFeaturesToTrack+PyrLK). Prefer homography over 2D affine when forward/dolly motion is likely — but note that **no 2D warp can remove parallax**. Fall back to `estimateAffinePartial2D` only if homography is degenerate.
2) **Dense optical flow + flow residual**: compute dense flow (Farneback or DIS) between prev and curr. Build predicted flow by projecting the pixel grid through `H`: `flow_pred(x,y) = Hp(x,y) - (x,y)`. Compute `residual = flow_obs - flow_pred` and `res_mag = ||residual||`. This isolates motion that disagrees with the global model — both in magnitude AND direction (so parallax that is colinear with epipolar flow does not blow up as easily as raw absdiff).
3) **Valid region**: warp an all-ones mask with the same `H` (`cv2.warpPerspective`, nearest) to mark border-invalid pixels; exclude them from stats and output.
4) **Adaptive threshold (720p defaults)**: on `res_mag[valid]`, `thr = max(1.5 px, median + 4*1.4826*MAD)`. Keep the floor low — pedestrians are small; aggressive thresholds erase them.
5) **Morphology + area filter (720p defaults)**: `MORPH_OPEN` 3×3 then `MORPH_CLOSE` 11×11 to 15×15. Keep CC with area ≥ 0.3–1.0% of H*W (≈2500–7000 px at 720p). Finally **dilate the kept mask by 2–3 px** to improve IoU / Boundary-IoU against GT. Prefer tighter thresholds + modest min_area over heavy smoothing (small pedestrians collapse to zero otherwise).
6) **Temporal consistency**: require each surviving component to overlap (any pixel) with a surviving component in the previous or next sampled frame — i.e. **persist across ≥2 consecutive frames**. Optionally temporal-median masks across a 3-frame window to kill parallax flicker.
7) **Frame-0 policy**: never emit an empty mask for frame 0. Compute the mask using the pair (frame 0, frame 1) and assign it to frame 0 (and separately recompute for frame 1 using (1,2)). An empty frame-0 mask guarantees IoU=0 on that frame.
8) **CSR encoding**: for final bool mask  
   - `rows, cols = nonzero(mask)`  
   - `indices = cols.astype(int32)`; `data = ones(nnz, uint8)`  
   - `counts = bincount(rows, minlength=H)`; `indptr = cumsum(counts, prepend=0)`  
   - store as `f_{i}_data/indices/indptr`

# Code sketch
```python
# 1) Global homography (prev -> curr) from feature correspondences
Hmat, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)

# 2) Dense observed flow
flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None,
                                    0.5, 3, 25, 3, 7, 1.5, 0)

# 3) Predicted flow from homography on pixel grid
ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
ones = np.ones_like(xs)
grid = np.stack([xs, ys, ones], axis=-1).reshape(-1, 3).T   # 3xN
proj = Hmat @ grid
proj = (proj[:2] / proj[2:3]).T.reshape(H, W, 2)
flow_pred = proj - np.stack([xs, ys], axis=-1)
residual = flow - flow_pred
res_mag = np.linalg.norm(residual, axis=-1)

# 4) Valid region (exclude warped-out borders)
valid = cv2.warpPerspective(np.ones((H,W),np.uint8), Hmat, (W,H),
                            flags=cv2.INTER_NEAREST) > 0

# 5) Adaptive threshold on residual magnitude
vals = res_mag[valid]
med = np.median(vals)
mad = np.median(np.abs(vals - med))
thr = max(1.5, med + 4 * 1.4826 * mad)
raw = (res_mag > thr) & valid

# 6) Morphology + CC area filter (720p defaults)
k3  = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
k13 = cv2.getStructuringElement(cv2.MORPH_RECT, (13,13))
m = cv2.morphologyEx(raw.astype(np.uint8)*255, cv2.MORPH_OPEN,  k3)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k13)
min_area = int(0.005 * H * W)  # ~0.5% ≈ 4600 px at 720p
n, cc, stats, _ = cv2.connectedComponentsWithStats(m>0, connectivity=8)
kept = np.zeros_like(raw, dtype=bool)
for cid in range(1, n):
    if stats[cid, cv2.CC_STAT_AREA] >= min_area:
        kept |= (cc == cid)

# 7) Dilate slightly to improve IoU / Boundary-IoU
kept = cv2.dilate(kept.astype(np.uint8), k3, iterations=2).astype(bool)

# 8) Temporal persistence (apply after collecting per-pair raw masks):
#    final[i] = kept[i] AND (kept[i] overlaps kept[i-1] OR kept[i+1]) per-CC.
#    For frame 0: reuse the mask computed from pair (0,1).
```

# Self-check
- [ ] Masks only for sampled frames; keys match sampled indices.
- [ ] `shape` stored as `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`.
- [ ] Border fill not treated as foreground; threshold stats computed on valid region only.
- [ ] Threshold + morphology + area filter applied.
- [ ] **Frame 0 is non-empty**: computed from the (0,1) pair rather than left blank.
- [ ] **Coverage sanity**: mean per-frame foreground fraction is between ~0.1% and ~20% of pixels. If <0.1%, lower `thr` floor and/or `min_area`; if >20%, the homography likely failed (fallback or re-estimate).
- [ ] **Visual spot-check**: overlay a few masks on the RGB frames; masks should land on pedestrians/vehicles, not on building edges, ground texture, or image borders.
- [ ] **Parallax guard**: using flow-residual against a projected homography flow, not raw image absdiff — forward/dolly scenes otherwise produce massive parallax speckle.
- [ ] **Temporal consistency**: each kept component appears in ≥2 consecutive sampled frames (except at sequence ends).
