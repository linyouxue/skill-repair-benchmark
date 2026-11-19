---
name: dyn-object-masks
description: "Generate per-sampled-frame dynamic-object binary masks using motion residual after background-dominant global motion estimation; store as CSR (shape + f_i_{data,indices,indptr})."
---

# When to use
- You need to detect **moving objects** in a video with **camera motion**.
- You must output one **binary mask per sampled frame**, keyed by **sample index**.

# Key conventions (sample-index space)
- Let `S` be the number of sampled frames.
- The NPZ must contain:
  - `shape = [H, W]` (prefer `int32`)
  - for each sample index `i = 0..S-1`: `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr`

Do **not** key masks by original video frame numbers unless the prompt explicitly says so.

# Common failure modes (and fixes)
## 1) Global alignment is “hijacked” by a large moving object
If your estimated transform is dominated by a foreground mover, then:
- the mover looks static after warping → **false negatives** (missed dynamic object)
- background misaligns → **false positives** (background becomes “dynamic”)

**Fix:** estimate global motion from **background-dominant** evidence:
- enforce **spatial coverage** of inliers (grid-coverage check)
- use **robust/trimmed** statistics over dense flow
- iterate: estimate motion → provisional dynamic mask → re-estimate motion excluding dynamic pixels

## 2) Parallax / depth variation creates background residuals
A single affine/homography won’t fully align a 3D scene.

**Fix:** prefer **motion-residual** segmentation on optical flow (more robust than raw intensity differencing), and use robust thresholds.

## 3) Illumination changes trigger false masks
Raw `absdiff` in intensity is sensitive to exposure/flicker.

**Fix:**
- compute differences on **blurred** frames and/or **gradient magnitude**
- prefer **flow residual** when available

# Recommended approach (robust): optical-flow residual after fitting global motion
Instead of differencing pixel intensities after warping, segment pixels whose **measured motion** deviates from the **best-fit global background motion**.

## Important: avoid “mask = everything that doesn't fit my (wrong) model”
If your global background model is biased (e.g., by a large mover or by parallax), a pure residual threshold can mark huge background regions as dynamic.
Reusable mitigations:

1) **Two-stage fitting (translation-only → full model)**
Fit a translation-only baseline, then a richer model. Only keep the extra DOFs if they reduce robust residuals on presumed background.

2) **Soft dynamic exclusion and refit**
Use an initial residual threshold to exclude obvious movers and refit the global model on the remaining pixels (background-dominant).

3) **Optional appearance confirmation (precision boost, but can hurt recall)**
Intersecting with an appearance-change mask can reduce false positives from parallax/noise, but it can also remove true movers that have low appearance contrast (or are motion-blurred).

Reusable compromise:
- use motion-residual only by default
- enable appearance confirmation **only** when a frame’s raw motion mask is implausibly large (background likely marked dynamic)

## Workflow (be explicit about frame alignment)
**Critical alignment rule:** dense optical flow computed from `prev -> curr` is defined on the **source (`prev`) pixel grid**. Any residual mask you derive from that flow is therefore aligned to the **same source frame** (unless you explicitly warp it).

A robust way to produce a mask for **every** sampled frame `i` without off-by-one mistakes:

1) **Forward masks (aligned to frame `i`)**
   - For each pair `i -> i+1` (for `i=0..S-2`):
     - compute dense optical flow on a **downsampled** version of the frames
     - fit a low-DOF global background motion model to the flow using robust statistics
     - compute per-pixel residual magnitude `||flow - flow_global||` on the **frame `i` grid**
     - threshold residuals with `median + k*MAD` (adaptive per-pair)
     - clean with morphology + area filtering
     - upsample mask back to `(H,W)`
     - store as `mask[i]` (since it is aligned to frame `i`)

2) **Last-frame coverage**
   - To get `mask[S-1]`, either:
     - compute a **backward** mask from `S-1 -> S-2` (flow on the last frame grid), or
     - reuse/propagate the nearest available mask when motion is small.

3) *(Optional but often helps recall)* **Bidirectional union**
   - Also compute backward masks for `i -> i-1` (for `i=1..S-1`) and union them with forward masks:
     - `mask[i] = mask_fwd[i] OR mask_bwd[i]`
   This captures dynamics that are hard to see in one direction and avoids forcing `mask[0]` to be empty by design.

4) Encode each boolean `mask[i]` as CSR arrays (`data/indices/indptr`).

# CSR encoding (required)
For a final boolean mask `mask_bool` of shape `(H, W)`:
- `rows, cols = np.nonzero(mask_bool)`
- `indices = cols.astype(np.int32)`
- `data = np.ones(indices.size, dtype=np.uint8)` (or `bool`)
- `counts = np.bincount(rows.astype(np.int32), minlength=H)`
- `indptr = np.concatenate([[0], np.cumsum(counts)]).astype(np.int32)`

Store as:
- `f_{i}_data = data`
- `f_{i}_indices = indices`
- `f_{i}_indptr = indptr`  (must have length `H+1`)

# Code sketch (flow residual, downsampled)
```python
import numpy as np
import cv2

# Tunables (keep generic; avoid per-video hard-coding)
DOWNSAMPLE_MAX_W = 480  # compute flow on a smaller grid for speed

# Residual thresholding: tradeoff precision vs recall.
# If recall is low (masks nearly empty), decrease K_MAD slightly.
# If masks are too large (background marked dynamic), increase K_MAD.
K_MAD = 4.5             # typical range ~[4, 7]; lower -> higher recall

# MIN_RESID should be expressed in **full-res pixels** and scaled to the flow grid.
# (A fixed value on the downsampled grid is not resolution-robust.)
MIN_RESID_PX = 1.0      # full-res pixels

MIN_AREA = 0.0002       # fraction of image area on full-res mask

k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

def mad(x: np.ndarray) -> float:
    x = x.astype(np.float32).ravel()
    if x.size == 0:
        return 0.0
    med = float(np.median(x))
    return float(np.median(np.abs(x - med)))

def fit_translation_only(flow: np.ndarray, valid=None):
    """Fit translation-only (tx, ty) to dense flow on a grid (robust)."""
    u = flow[..., 0].astype(np.float32)
    v = flow[..., 1].astype(np.float32)
    if valid is None:
        valid = np.ones(u.shape, dtype=bool)
    tx = float(np.median(u[valid]))
    ty = float(np.median(v[valid]))
    return tx, ty

def fit_global_flow(flow: np.ndarray, valid=None):
    """Fit translation + zoom + roll coefficients to dense flow on a grid."""
    h, w = flow.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    x = (xx - cx).astype(np.float32)
    y = (yy - cy).astype(np.float32)

    u = flow[..., 0].astype(np.float32)
    v = flow[..., 1].astype(np.float32)

    if valid is None:
        valid = np.ones((h, w), dtype=bool)

    # ignore unstable border + tiny radius near center
    margin = max(2, int(0.02 * min(h, w)))
    ok = valid.copy()
    ok[:margin, :] = False
    ok[-margin:, :] = False
    ok[:, :margin] = False
    ok[:, -margin:] = False

    r2 = x * x + y * y
    ok &= (r2 > 25.0)

    # robust translation
    tx = float(np.median(u[valid]))
    ty = float(np.median(v[valid]))

    u0 = u - tx
    v0 = v - ty

    # robust zoom + roll via median projections
    k = float(np.median(((u0 * x + v0 * y) / r2)[ok])) if np.any(ok) else 0.0
    wcoef = float(np.median(((u0 * (-y) + v0 * x) / r2)[ok])) if np.any(ok) else 0.0

    return tx, ty, k, wcoef

def global_flow_field(h, w, tx, ty, k, wcoef):
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    x = (xx - cx).astype(np.float32)
    y = (yy - cy).astype(np.float32)
    u = tx + k * x + wcoef * (-y)
    v = ty + k * y + wcoef * (x)
    return np.stack([u, v], axis=-1).astype(np.float32)

def dyn_mask_from_pair(prev_gray, curr_gray, use_appearance_confirm: bool = False, max_raw_frac: float = 0.20):
    H, W = prev_gray.shape

    # Downsample for flow
    scale = min(1.0, DOWNSAMPLE_MAX_W / max(1.0, float(W)))
    if scale < 1.0:
        nh, nw = int(round(H * scale)), int(round(W * scale))
        prev_s = cv2.resize(prev_gray, (nw, nh), interpolation=cv2.INTER_AREA)
        curr_s = cv2.resize(curr_gray, (nw, nh), interpolation=cv2.INTER_AREA)
    else:
        prev_s, curr_s = prev_gray, curr_gray

    # Dense flow (Farneback is widely available)
    flow = cv2.calcOpticalFlowFarneback(
        prev_s, curr_s, None,
        pyr_scale=0.5, levels=3, winsize=21,
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
    )

    # --- Two-stage fit + refit excluding obvious dynamics ---
    # 1) translation-only baseline
    tx0, ty0 = fit_translation_only(flow)
    flow_t = global_flow_field(flow.shape[0], flow.shape[1], tx0, ty0, 0.0, 0.0)
    resid_t = np.linalg.norm(flow - flow_t, axis=-1)

    # 2) full model
    tx, ty, k, wcoef = fit_global_flow(flow)
    flow_g = global_flow_field(flow.shape[0], flow.shape[1], tx, ty, k, wcoef)
    resid = np.linalg.norm(flow - flow_g, axis=-1)

    # If the full model does not improve robust residuals, fall back to translation-only.
    # (This reduces false dynamics from overfitting zoom/roll on parallax or movers.)
    med_t = float(np.median(resid_t))
    med_full = float(np.median(resid))
    sigma_full = 1.4826 * mad(resid)
    if med_full > med_t - 0.25 * max(1e-6, sigma_full):
        tx, ty, k, wcoef = tx0, ty0, 0.0, 0.0
        flow_g = flow_t
        resid = resid_t

    # Exclude obvious dynamics and refit (helps when a large mover biases the fit)
    med = float(np.median(resid))
    sigma = 1.4826 * mad(resid)
    thr_excl = max(0.30, med + 2.5 * sigma)
    valid2 = (resid <= thr_excl)
    tx2, ty2, k2, wcoef2 = fit_global_flow(flow, valid=valid2)
    flow_g2 = global_flow_field(flow.shape[0], flow.shape[1], tx2, ty2, k2, wcoef2)
    resid2 = np.linalg.norm(flow - flow_g2, axis=-1)

    # Compute robust center/scale on the refit residuals *restricted to presumed background*.
    # This avoids setting thresholds based on moving-object pixels.
    resid_bg = resid2[valid2] if np.any(valid2) else resid2
    med2 = float(np.median(resid_bg))
    sigma2 = 1.4826 * mad(resid_bg)
    # Scale MIN_RESID_PX from full-res to the flow grid.
    min_resid_grid = float(MIN_RESID_PX) * float(scale)
    thr = max(min_resid_grid, med2 + K_MAD * sigma2)

    raw = (resid2 > thr).astype(np.uint8) * 255
    raw = cv2.morphologyEx(raw, cv2.MORPH_OPEN, k_open)
    raw = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, k_close)

    # Optional: appearance confirmation on the SAME grid as `raw`.
    # Best used conditionally (e.g., only when the raw mask is implausibly large),
    # because intersecting with appearance change can reduce recall.
    raw_frac = float(np.count_nonzero(raw)) / float(raw.size)
    if use_appearance_confirm or (raw_frac > float(max_raw_frac)):
        prev_blur = cv2.GaussianBlur(prev_s, (5, 5), 0)
        curr_blur = cv2.GaussianBlur(curr_s, (5, 5), 0)
        diff = cv2.absdiff(prev_blur, curr_blur)
        d_med = float(np.median(diff))
        d_sigma = 1.4826 * mad(diff)
        d_thr = d_med + 3.0 * d_sigma
        app = (diff > d_thr).astype(np.uint8) * 255
        app = cv2.morphologyEx(app, cv2.MORPH_OPEN, k_open)
        raw = cv2.bitwise_and(raw, app)

    # Upsample back to full-res
    if scale < 1.0:
        raw = cv2.resize(raw, (W, H), interpolation=cv2.INTER_NEAREST)

    # Area filter on full-res
    min_area_px = int(MIN_AREA * H * W)
    num, cc, stats, _ = cv2.connectedComponentsWithStats((raw > 0).astype(np.uint8), connectivity=8)
    out = np.zeros((H, W), dtype=bool)
    for cid in range(1, num):
        if int(stats[cid, cv2.CC_STAT_AREA]) >= min_area_px:
            out |= (cc == cid)

    return out

# Example: produce one mask per sampled frame (sample-index aligned)
# NOTE: dyn_mask_from_pair(prev, curr) returns a mask aligned to `prev`.
# For best coverage, you can also compute backward masks and union them.

def build_masks(grays):
    """Return list[mask_bool] length S, where mask[i] aligns to grays[i]."""
    S = len(grays)
    if S == 0:
        return []
    if S == 1:
        H, W = grays[0].shape
        return [np.zeros((H, W), dtype=bool)]

    masks_fwd = [None] * S
    masks_bwd = [None] * S

    # Forward flow gives masks aligned to frames 0..S-2
    for i in range(S - 1):
        masks_fwd[i] = dyn_mask_from_pair(grays[i], grays[i + 1])

    # Backward flow gives masks aligned to frames 1..S-1
    for i in range(1, S):
        masks_bwd[i] = dyn_mask_from_pair(grays[i], grays[i - 1])

    # Union (treat missing ends as all-false)
    H, W = grays[0].shape
    out = []
    for i in range(S):
        m = np.zeros((H, W), dtype=bool)
        if masks_fwd[i] is not None:
            m |= masks_fwd[i]
        if masks_bwd[i] is not None:
            m |= masks_bwd[i]
        out.append(m)

    return out
```

# Optional: combine motion residual with stabilized appearance diff (precision boost)
If you still get many false positives:
- build an affine/homography from the fitted global motion and warp `prev` into `curr`
- compute `absdiff` on **blurred** or **gradient magnitude** images
- keep pixels that are dynamic in **both** motion-residual and appearance-diff masks

# Self-check
- [ ] Masks are produced for **exactly** `S` sampled frames and keyed by `i=0..S-1`.
- [ ] `shape == [H, W]` and CSR arrays satisfy:
  - `len(indptr) == H+1`
  - `indptr[-1] == indices.size == data.size`
  - indices within `[0, W)`
- [ ] If a large moving object dominates the scene, ensure global motion estimation is not fit only to that object (use coverage checks / robust flow fitting).
- [ ] Sanity: compute per-frame foreground fraction `nnz/(H*W)`; if it is near 0 for all frames or near 1 for many frames, revisit thresholds/global motion.
