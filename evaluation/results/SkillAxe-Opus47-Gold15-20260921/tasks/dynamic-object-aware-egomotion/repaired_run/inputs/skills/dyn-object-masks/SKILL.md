---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation, output CSR sparse format."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.

# Key failure modes to avoid
Two extremes both destroy IoU and must be actively guarded against:
- **Flooded masks** (foreground fraction ≳ 10% of the image on most frames): usually caused by residual global-motion misalignment (parallax under dolly/large translation, or an affine model where a homography is needed). The whole scene lights up.
- **Empty masks** (foreground fraction ≈ 0 on most frames): usually caused by an overly aggressive threshold, over-erosion, or a minimum-area filter that is too large.

Aim for per-frame foreground fraction roughly in the **0.2%–8%** band for typical scenes with one or a few moving objects. Treat sustained values outside `[0.05%, 15%]` as a red flag and re-tune before submitting.

# Workflow
1) **Global alignment**: warp previous gray frame to current using an estimated transform.
   - Default to **homography** (`cv2.findHomography` with RANSAC) rather than affine when the camera translates significantly (dolly in/out, walking POV), because affine cannot cancel parallax-induced apparent motion of the background.
   - Fall back to `estimateAffinePartial2D` only if homography estimation fails or produces a near-degenerate matrix.
2) **Valid region**: also warp an all-ones mask to get `valid` pixels; **erode** the valid mask by a few pixels to discard border/interpolation artifacts before differencing.
3) **Difference + adaptive threshold**: `diff = abs(curr - warp_prev)`; on `diff[valid_eroded]` compute `median + k·1.4826·MAD` with `k` in `[3, 5]`; enforce a reasonable minimum threshold (e.g. `>= 15`) to avoid triggering on sensor noise. A light Gaussian blur on both frames before the diff reduces sub-pixel misalignment noise.
4) **Morphology + area filter**: open (3×3 or 5×5) then close (7×7 to 11×11); keep connected components above a minimum area. Suggested starting range: `min_area` between `0.05%` and `0.3%` of `H*W` (e.g. ~460–2800 px for 720p). Larger `min_area` removes noise but also small real objects — do not push past `~0.5%` without evidence.
5) **Coverage check (mandatory)**: after building each frame's mask, compute `fg_frac = mask.mean()`.
   - If the mean `fg_frac` across sampled frames is `> ~15%`, alignment is failing — switch/verify homography, blur more, or raise threshold `k`.
   - If the mean `fg_frac` is `< ~0.05%` on scenes that clearly contain motion, threshold or `min_area` is too aggressive — lower them.
   - Do not submit before this loop stabilizes.
6) **CSR encoding**: for the final bool mask
   - `rows, cols = nonzero(mask)`
   - `indices = cols.astype(int32)`; `data = ones(nnz, uint8)`
   - `counts = bincount(rows, minlength=H)`; `indptr = cumsum(counts, prepend=0).astype(int32)`
   - store as `f_{i}_data/indices/indptr`

# Code sketch
```python
# 1) Global alignment via homography (parallax-tolerant); affine fallback.
p0 = cv2.goodFeaturesToTrack(prev_gray, maxCorners=2000, qualityLevel=0.01,
                             minDistance=8, blockSize=7)
p1, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, p0, None,
                                     winSize=(21,21), maxLevel=3)
g0 = p0[st.reshape(-1)==1]; g1 = p1[st.reshape(-1)==1]
Hmat, _ = cv2.findHomography(g0, g1, cv2.RANSAC, 3.0)
if Hmat is not None:
    warped_prev = cv2.warpPerspective(prev_gray, Hmat, (W,H), flags=cv2.INTER_LINEAR, borderValue=0)
    valid = cv2.warpPerspective(np.ones((H,W),np.uint8), Hmat, (W,H),
                                flags=cv2.INTER_NEAREST) > 0
else:
    # affine fallback ...
    pass

valid = cv2.erode(valid.astype(np.uint8),
                  cv2.getStructuringElement(cv2.MORPH_RECT,(7,7))) > 0

curr_b = cv2.GaussianBlur(curr_gray, (5,5), 0)
prev_b = cv2.GaussianBlur(warped_prev, (5,5), 0)
diff = cv2.absdiff(curr_b, prev_b)
vals = diff[valid]
med = float(np.median(vals)); mad = float(np.median(np.abs(vals-med)))
thr = max(15.0, med + 3.5*1.4826*mad)  # tune k in [3,5]
raw = (diff > thr) & valid

k3 = cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
k7 = cv2.getStructuringElement(cv2.MORPH_RECT,(7,7))
m = cv2.morphologyEx(raw.astype(np.uint8)*255, cv2.MORPH_OPEN, k3)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k7)

n, cc, stats, _ = cv2.connectedComponentsWithStats((m>0).astype(np.uint8), connectivity=8)
min_area = max(200, int(0.0008*H*W))  # ~0.08% of image; tune in [0.05%, 0.3%]
mask = np.zeros((H,W), dtype=bool)
for cid in range(1,n):
    if stats[cid, cv2.CC_STAT_AREA] >= min_area:
        mask |= (cc==cid)

fg_frac = float(mask.mean())  # inspect across all frames; retune if extreme
```

# Tuning loop (do this before submitting)
1. Run the pipeline on all sampled frames and record `fg_frac` per frame.
2. Compute `mean` and `max` of `fg_frac`.
3. If `mean > 0.15` or many frames > 0.25: alignment/threshold too permissive → use homography (not affine), blur more, or raise threshold `k` or `min_area`.
4. If `mean < 0.001` and the video clearly contains moving objects: too strict → lower threshold `k`, reduce `min_area`, shrink morphology closing.
5. Only submit when the distribution is plausible (typical band `0.2%–8%`).

# Self-check
- [ ] Masks only for sampled frames; keys match sampled indices.
- [ ] `shape` stored as `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`.
- [ ] Border fill not treated as foreground; threshold stats computed on eroded valid region only.
- [ ] Threshold + morphology + area filter applied.
- [ ] Homography used when camera translates significantly; affine only as fallback.
- [ ] Per-frame foreground fraction inspected; not near-zero and not near-total on scenes with motion.
