---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation, output CSR sparse format."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.

# Choosing a method
A 2D global warp (affine/homography) + image differencing is simple but **fails on scenes with strong parallax** — e.g. forward "dolly in" camera motion, or wide-FOV outdoor walks where near objects move very differently from far background. In those cases pure image differencing flags large static-but-near regions as dynamic (very high mask fill, e.g. >10% of the image).

Use one of the two approaches below based on the scene. **Prefer the flow-residual approach whenever the egomotion step reports non-trivial Dolly In/Out, or `dx/dy` vary noticeably across the image.** If you have the time budget it is usually safer to just run Method B — it degrades gracefully on planar scenes too.

> **IoU rule of thumb before you tune anything.** Mask IoU is asymmetric: false positives on static-but-near geometry (parked vehicles, signs, hanging stall items, foreground foliage) cost as much ground-truth-less area as they cover, and they can easily outweigh any extra true-positive recall you squeezed out. In a parallax-heavy scene **an empty mask is a better default than a 4–8 % "medium-fill" mask covering plausible-looking near-field clutter** — IoU on a frame with no GT motion is 0 either way for the mask itself but the overall metric penalises the FP area, and mask IoU on a frame that *does* contain a small real object is strongly degraded by any extra FP region around it. When your visual sanity check cannot *point at a clearly moving object* in a given frame's mask, prefer to ship empty for that frame.

## Method A — Image differencing after global warp (planar / small parallax)
1) **Global alignment**: warp previous gray frame to current using estimated affine/homography.
2) **Valid region**: also warp an all-ones mask to get `valid` pixels, avoiding border fill.
3) **Difference + adaptive threshold**: `diff = abs(curr - warp_prev)`; on `diff[valid]` compute `median + K * 1.4826 * MAD` (start with `K≈3–5`); clip with a reasonable minimum threshold to avoid triggering on noise.
4) **Border erosion**: erode `valid` by a few pixels before thresholding to discard warp-boundary artifacts.
5) **Morphology + area filter**: open (small kernel) then close (larger kernel); keep connected components above a minimum area (tune as fraction of image area or a fixed pixel threshold).

```python
warped_prev = cv2.warpAffine(prev_gray, M, (W,H), flags=cv2.INTER_LINEAR, borderValue=0)
valid = cv2.warpAffine(np.ones((H,W),np.uint8), M, (W,H), flags=cv2.INTER_NEAREST) > 0
valid_er = cv2.erode(valid.astype(np.uint8), k7, iterations=1) > 0
diff = cv2.absdiff(curr_gray, warped_prev)
vals = diff[valid_er]
med = np.median(vals); mad = np.median(np.abs(vals - med))
thr = max(15.0, med + 3.0 * 1.4826 * mad)
raw = (diff > thr) & valid_er
m = cv2.morphologyEx(raw.astype(np.uint8)*255, cv2.MORPH_OPEN, k3)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k9)
```

## Method B — Dense optical flow residual (parallax / dolly / wide-FOV)
Idea: fit a *global* parametric flow model to the dense flow, then threshold the per-pixel residual magnitude. Pixels whose flow does not fit the global camera-induced flow are candidate dynamic pixels. This is much more robust under dolly-in / lateral-translation parallax than raw image differencing because the model is fit to the actual flow distribution, not to pixel intensities.

1) **Dense flow**: `cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, ...)` → `flow` shape `(H, W, 2)`.
2) **Global parametric flow model (robust)**. Model choice matters a lot when the scene has parallax, and this is the single biggest IoU driver in forward-motion scenes:
   - `cv2.estimateAffinePartial2D` is only **4 DOF** (rotation + isotropic scale + tx + ty). Under *forward* translation the true per-pixel flow has a strong radial / diverging pattern that a 4-DOF model cannot absorb, so even static near-field regions end up with large residuals.
   - `cv2.estimateAffine2D` (full 6-DOF affine) is strictly better but still **purely linear in `(x, y)`**. Parallax from forward translation is intrinsically **quadratic** in image coordinates (the focus-of-expansion flow field scales roughly like `(x - cx)` and `(y - cy)` *times* a per-pixel depth factor that itself varies with position). A linear model therefore leaves a systematic quadratic residual that looks exactly like a smooth near-background blob — which the detector will happily flag as a moving object, tanking IoU.
   - **For any scene where the egomotion step reports Dolly In/Out or a wide-FOV walking shot, fit a 12-parameter biquadratic model directly** on the subsampled flow: `u = a0 + a1*x + a2*y + a3*x^2 + a4*x*y + a5*y^2` and `v` has six analogous coefficients. Solve with a plain linear least squares, then re-weight with a few Welsch / Huber IRLS passes so moving-object pixels get softly down-weighted without the fit collapsing onto them (hard 0/1 inlier/outlier weights can lock onto the wrong inlier set; **always use soft** weights). Verify the effective inlier mass covers a majority of the frame; if the solve blows up or returns NaN, fall back to `cv2.estimateAffine2D` (6-DOF) with RANSAC, then to `cv2.estimateAffinePartial2D`, then finally to the identity flow.
   - The biquadratic model is cheap (12 unknowns, a few hundred samples from a 16-px grid, three IRLS passes). Do not reserve it as an "escalation" — make it the default when any Dolly label is present. The one case where a 6-DOF affine is enough is a pure Pan/Tilt/Roll with no translation, which has no parallax.
3) **Residual**: predict expected `(u_pred, v_pred)` for every pixel and compute `res = sqrt((u-u_pred)**2 + (v-v_pred)**2)`.
4) **Border suppression (parallax heavy scenes)**: with forward translation, the un-modelable radial component peaks at the image perimeter and drops near the focus of expansion. Build a `valid` mask that erodes a few % of the image on each side (6–8% of min(H, W) when a Dolly label is present; 3–4% for pure pan/tilt) and only apply the detection threshold inside `valid`; outside `valid`, force the mask to False. This trades a thin rim of recall for a big precision gain and is usually a net win when a 2D model is being asked to explain genuinely 3D flow.
5) **Threshold**: `thr = max(floor, med + K * 1.4826 * MAD)`. Balanced defaults:
   - pixel `floor ≈ 1.5–2.5 px`, `K ≈ 3.0–4.0`.
   - A tight `K≥5` with a 3 px floor is one common failure mode — it leaves many frames with an empty mask while an obvious moving object is clearly visible in `res`. If you ever see >30% of frames come out completely empty, back the threshold off.
   - The opposite failure mode is also common: `K≤2.5` and no border suppression produce >6% mask fill on frames with strong forward motion — that is almost entirely parallax leakage, **not** moving objects, and it tanks mask IoU. If per-frame fill crosses a precision ceiling (see "Sanity window" below), tighten *this* frame's threshold instead of shipping as-is.
6) **Morphology + area filter**: a *small* open (e.g. 3×3) only to kill isolated speckle, a *larger* close (e.g. 9×9 or 11×11) to fuse edge-only detections into filled blobs, then an optional small dilation (e.g. 3×3) to recover object boundaries that erosion-like opens may have shaved. Keep connected components above a **small** minimum area (~0.08–0.20% of image area is a good default; much smaller floods the mask with scattered parallax speckle, much larger drops medium objects at 720p).
7) **Component shaping (replaces blind whole-frame reset)**. When the fill ceiling is tripped (see below), do **not** simply set `mask[:] = False`: a scene with a real moving object plus parallax leakage will have both in the mask, and nuking the frame destroys all recall there. Instead score each remaining connected component by a combination of (a) compactness `area / bbox_area` (real objects are blob-shaped; parallax leakage is typically thin/elongated along image edges), (b) distance of its centroid from the image boundary (parallax is edge-concentrated; real objects are usually interior), and (c) size (prefer the one or two largest *qualifying* blobs over a long tail of specks). Keep only components passing a soft score and whose aggregate fill lands in a plausible band (roughly 0.3–8 %); if nothing qualifies after that, *then* fall through to empty.
8) **Caveat**: even a biquadratic 2D flow model cannot fully represent parallax under forward translation at very close range — the true depth-dependent component is non-polynomial. Some residual leakage along near-camera foreground edges is expected and cannot be fully removed without depth. Tightening `K`, raising `min_area`, widening border suppression, and the component-shaping step are the four dials; do not loop forever hand-tuning. Prefer a middle setting — undershooting recall and overshooting precision both lose IoU.

```python
flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None,
        pyr_scale=0.5, levels=3, winsize=21, iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
u, v = flow[..., 0], flow[..., 1]
H2, W2 = u.shape

# --- Global flow fit: biquadratic (12 params) when a dolly/translation is present,
#     linear 6-DOF affine otherwise. Both are solved on the same subsampled grid.
stride = 16
ys, xs = np.mgrid[0:H2:stride, 0:W2:stride]
xs_f = xs.ravel().astype(np.float64)
ys_f = ys.ravel().astype(np.float64)
u_s = u[ys, xs].ravel().astype(np.float64)
v_s = v[ys, xs].ravel().astype(np.float64)

# Normalise coordinates for numerical conditioning on the quadratic terms.
cx, cy = (W2 - 1) * 0.5, (H2 - 1) * 0.5
scl = 0.5 * max(W2, H2)
xn = (xs_f - cx) / scl
yn = (ys_f - cy) / scl

def _fit_biquadratic(xn, yn, u_s, v_s):
    # Columns: [1, x, y, x^2, x*y, y^2]
    A = np.stack([np.ones_like(xn), xn, yn, xn * xn, xn * yn, yn * yn], axis=1)
    w = np.ones_like(xn)
    for _ in range(3):  # Welsch IRLS; soft weights, never 0/1.
        sw = np.sqrt(np.maximum(w, 1e-8))  # WLS: scale rows by sqrt of weight.
        AW = A * sw[:, None]
        try:
            coef_u, *_ = np.linalg.lstsq(AW, u_s * sw, rcond=None)
            coef_v, *_ = np.linalg.lstsq(AW, v_s * sw, rcond=None)
        except np.linalg.LinAlgError:
            return None, None
        if not (np.all(np.isfinite(coef_u)) and np.all(np.isfinite(coef_v))):
            return None, None
        ru = u_s - A @ coef_u
        rv = v_s - A @ coef_v
        r = np.sqrt(ru * ru + rv * rv) + 1e-6
        # Welsch width ≈ 2*MAD-scaled sigma; soft, no hard cutoff.
        sigma = max(0.5, 1.4826 * np.median(r))
        w = np.exp(-(r / (2.0 * sigma)) ** 2)
    # Verify a majority of samples kept non-trivial weight; otherwise reject the fit.
    if float(np.mean(w > 0.1)) < 0.5:
        return None, None
    return coef_u, coef_v

coef_u, coef_v = _fit_biquadratic(xn, yn, u_s, v_s)

yy, xx = np.mgrid[0:H2, 0:W2].astype(np.float64)
xxn = (xx - cx) / scl
yyn = (yy - cy) / scl
if coef_u is not None and coef_v is not None:
    B = np.stack([np.ones_like(xxn), xxn, yyn, xxn * xxn, xxn * yyn, yyn * yyn], axis=-1)
    u_pred = B @ coef_u
    v_pred = B @ coef_v
else:
    # Linear-only fallbacks.
    src = np.stack([xs_f, ys_f], axis=1).astype(np.float32)
    dst = np.stack([xs_f + u_s, ys_f + v_s], axis=1).astype(np.float32)
    M_flow, _ = cv2.estimateAffine2D(src, dst, method=cv2.RANSAC,
                                     ransacReprojThreshold=2.0, maxIters=2000, confidence=0.99)
    if M_flow is None:
        M_flow, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                                ransacReprojThreshold=2.0, maxIters=2000, confidence=0.99)
    if M_flow is None:
        M_flow = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
    u_pred = M_flow[0, 0] * xx + M_flow[0, 1] * yy + M_flow[0, 2] - xx
    v_pred = M_flow[1, 0] * xx + M_flow[1, 1] * yy + M_flow[1, 2] - yy

res = np.sqrt((u - u_pred) ** 2 + (v - v_pred) ** 2).astype(np.float32)

# --- Border suppression (shrinks parallax rim; keep interior detections) ---
# Widen the border under a strong translation signal (dolly present / big mean flow mag).
mean_flow_mag = float(np.sqrt(u.mean() ** 2 + v.mean() ** 2))
# Parallax-heavy border suppression: widen to ~10% under strong forward translation.
# Clutter at the image rim (signs, parked vehicles, awnings) is the dominant source of
# false-positive mass under Dolly In/Out and almost never contains the GT dynamic object.
if mean_flow_mag > 2.0:
    border_frac = 0.10
elif mean_flow_mag > 1.0:
    border_frac = 0.07
else:
    border_frac = 0.04
bx = max(8, int(border_frac * W2))
by = max(8, int(border_frac * H2))
valid = np.zeros_like(res, dtype=bool)
valid[by:H2 - by, bx:W2 - bx] = True

# --- Adaptive threshold on the valid interior; retry tighter if fill explodes ---
def _detect(K, floor):
    vals = res[valid]
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med)))
    thr = max(floor, med + K * 1.4826 * mad)
    raw = ((res > thr) & valid).astype(np.uint8) * 255
    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    k9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    m = cv2.morphologyEx(raw, cv2.MORPH_OPEN, k3)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k9)
    m = cv2.dilate(m, k3, iterations=1)
    num, labels_cc, stats, _ = cv2.connectedComponentsWithStats(
        (m > 0).astype(np.uint8), connectivity=8)
    min_area = max(100, int(0.0012 * H2 * W2))  # ≈0.12% of image, with an absolute floor
    out = np.zeros_like(m, dtype=bool)
    kept = []
    for lab in range(1, num):
        if stats[lab, cv2.CC_STAT_AREA] >= min_area:
            out |= (labels_cc == lab)
            kept.append(lab)
    return out, labels_cc, stats, kept

# Threshold defaults are stricter when the egomotion step signals forward translation.
# Under Dolly In/Out + wide-FOV walking, the residual field around static-but-near
# geometry (parked vehicles, awnings, foliage) sits right on the shoulder of the MAD
# distribution — a K≈3 cutoff slides easily into that shoulder and starts shipping
# static clutter as "dynamic". Pre-emptive tightening is cheaper than a retry ladder.
# `scene_has_dolly` should be computed once from the egomotion step's labels, e.g.
#   scene_has_dolly = any("Dolly" in lbl for lbls in per_frame_labels for lbl in lbls)
if scene_has_dolly and mean_flow_mag > 2.0:
    K_default, floor_default = 4.0, 3.0
elif scene_has_dolly or mean_flow_mag > 1.5:
    K_default, floor_default = 3.5, 2.5
else:
    K_default, floor_default = 3.0, 2.0

mask, labels_cc, stats, kept = _detect(K=K_default, floor=floor_default)
fill = float(mask.mean())

def _shape_score(labels_cc, stats, lab, H2, W2):
    # compactness (area / bbox_area) + interior preference (1 - normalised edge proximity)
    x0 = stats[lab, cv2.CC_STAT_LEFT]
    y0 = stats[lab, cv2.CC_STAT_TOP]
    w0 = stats[lab, cv2.CC_STAT_WIDTH]
    h0 = stats[lab, cv2.CC_STAT_HEIGHT]
    area = stats[lab, cv2.CC_STAT_AREA]
    bbox_area = max(1, w0 * h0)
    compact = area / bbox_area
    cxc = x0 + 0.5 * w0
    cyc = y0 + 0.5 * h0
    d_edge = min(cxc / W2, (W2 - cxc) / W2, cyc / H2, (H2 - cyc) / H2)
    interior = min(1.0, d_edge / 0.15)  # saturates once centroid is >15% in
    aspect = max(w0, h0) / max(1, min(w0, h0))
    thin_pen = 1.0 if aspect < 6.0 else 0.4  # thin edge-hugging rims get penalised
    return compact * interior * thin_pen, area

# Precision guard: when the detector overfills, tighten and then keep only the
# highest-scoring interior blobs. For Dolly scenes the guard runs even on
# moderately-filled frames because a 3–6 % mask of static-but-near clutter is
# the dominant failure mode and is worse for IoU than an empty frame.
guard_trip = 0.04 if scene_has_dolly else 0.08
if fill > guard_trip:
    tighter, labels_cc2, stats2, kept2 = _detect(K=K_default + 1.5, floor=floor_default + 1.0)
    if float(tighter.mean()) < fill:
        mask, labels_cc, stats, kept = tighter, labels_cc2, stats2, kept2
        fill = float(mask.mean())
    if kept:
        scored = [(lab, *_shape_score(labels_cc, stats, lab, H2, W2)) for lab in kept]
        # Prefer compact, interior, non-thin blobs; keep up to the 2 best whose sum
        # stays inside the plausible band (~3% max under a Dolly label).
        scored.sort(key=lambda t: (-t[1], -t[2]))  # best score first, then area
        picked = np.zeros_like(mask, dtype=bool)
        used = 0.0
        # Stricter shape bar under Dolly: the typical parallax blob is modestly
        # compact (compact≈0.4–0.6) and its centroid can land several % in from
        # the rim, which still produces a non-trivial unshaped score. Require a
        # higher shape score to actually ship.
        shape_bar = 0.25 if scene_has_dolly else 0.12
        area_cap = 0.03 if scene_has_dolly else 0.06
        used_cap = 0.02 if scene_has_dolly else 0.04
        for lab, sc, area in scored:
            if sc < shape_bar:
                continue
            frac = area / float(H2 * W2)
            if used + frac > area_cap:
                continue
            picked |= (labels_cc == lab)
            used += frac
            if used > used_cap:
                break
        # In a Dolly scene an *unverifiable* mask (no blob cleared the shape bar)
        # is better shipped empty than shipped as leftover residual mass — IoU
        # on an empty mask is at worst 0, whereas a parallax-FP mask actively
        # degrades the per-frame IoU through the union term.
        if picked.any():
            mask = picked
        elif scene_has_dolly:
            mask[:] = False
        fill = float(mask.mean())
    elif scene_has_dolly:
        # No qualifying components at all under a Dolly scene ⇒ parallax, not motion.
        mask[:] = False
        fill = 0.0
```

## Temporal persistence gate (parallax vs. motion discriminator)
Parallax leakage is anchored to the *image* (near-field clutter at a fairly fixed image position relative to the forward-translation vector): a pixel flagged on one frame tends to stay roughly in the same image location across neighbouring frames. A genuinely moving object is anchored to the *scene* and typically drifts across the image at a different rate than the background flow. A simple persistence check exploits this:

```python
# After all per-frame masks are produced (and temporally fused if you use that step),
# compute a *dense-coordinates* image-space persistence map and down-weight pixels
# that are "on" in most frames — those are almost certainly static-but-near clutter.
persistence = np.mean(np.stack(dense_masks, axis=0), axis=0)   # shape (H, W), float
HOT = 0.60  # fraction of frames above which a pixel is treated as static clutter
hot_mask = persistence > HOT
for k in range(n_samples):
    dense_masks[k] &= ~hot_mask
```

This step is cheap, data-free, and is a surprisingly strong parallax filter when the camera translation is roughly monotonic (dolly-in walking shot, long pan). Skip it when the shot is a cut-up multi-shot sequence where "static" geometry legitimately changes position across the clip.

# Two-sided temporal fusion (recommended)
A single prev→curr residual can miss an object on the frame where it momentarily overlaps background flow. For frame `k` with `1 <= k <= n_samples-2`, compute masks from both directions and **union** them:

```python
mask_fwd  = mask_from_flow(sampled_gray[k-1], sampled_gray[k])   # (k-1) -> k
mask_bwd  = mask_from_flow(sampled_gray[k],   sampled_gray[k+1]) # k -> (k+1)
mask_k    = mask_fwd | mask_bwd
```

For the last frame `k = n_samples-1` use only `mask_from_flow(sampled_gray[k-1], sampled_gray[k])`.

Union amplifies both signal and noise. When border suppression is on and the per-frame precision guard is in place, union is still a net win because the residual leakage pattern tends to be similar on the two sides and the extra OR mostly adds genuine object recall. If, after union, a frame still has fill > ~8% in a Dolly scene (or > ~15% otherwise), re-run the same component-shaping step (compact + interior + size scoring) on the union mask before shipping; **under a Dolly label the union is particularly prone to amplifying near-field clutter because the forward FoE residual is similar on both the prev→curr and curr→next sides, so the union adds parallax on top of parallax rather than cancelling it**. Prefer intersection (`&`) over union (`|`) when `scene_has_dolly` and the mean flow magnitude is >~2 px — it keeps only pixels that are flagged consistently from both sides, which is a strong parallax filter. Fall through to empty only when no component qualifies after shaping.

# Frame 0 handling
- Sampled frame 0 has no previous frame. **Do not blindly emit an all-False mask** — if the video has moving objects, frame 0 almost certainly has them too and an empty mask scores zero recall there.
- Compute the forward flow from frame 0 → frame 1 and use the resulting mask for frame 0 as well. Equivalently: `mask_0 = mask_from_flow(sampled_gray[0], sampled_gray[1])`.
- Still write `f_0_data/indices/indptr` so the NPZ frame count matches `n_samples`, whether the mask is empty or not.

# CSR encoding (both methods)
For the final boolean `mask`:
- `rows, cols = np.nonzero(mask)`
- `indices = cols.astype(np.int32)`
- `data = np.ones(indices.size, dtype=np.uint8)`
- `counts = np.bincount(rows, minlength=H)`
- `indptr = np.concatenate(([0], np.cumsum(counts))).astype(np.int32)`  # length H+1
- Store under keys `f_{k}_data`, `f_{k}_indices`, `f_{k}_indptr` where `k` is the **sampled** frame index.
- Store `shape = np.array([H, W], dtype=np.int32)` once in the NPZ.
- An empty mask has `data.size==0`, `indices.size==0`, and `indptr` of length `H+1` filled with zeros.

# Sanity window before shipping
After generating all masks, compute the per-frame fill ratio and check **both** sides of the window:

- **Floor**: if the **mean** fill across frames is < ~0.1%, or if a large fraction of frames (e.g. >30%) is exactly 0%, your detector is almost certainly too conservative — relax `K` by ~0.5–1.0, drop the pixel floor to ~1.0, or halve `min_area`, and recompute. Do not ship masks that are empty on most frames in a scene that clearly contains motion.
- **Ceiling**: the ceiling depends on the egomotion label mix:
  - *No Dolly label anywhere in the clip (static / pan / tilt only)*: mean fill > ~6–8% or a single frame > ~10% signals parallax leakage; aim for a mean fill in ~0.5–4%.
  - *Any frame carries a Dolly label (forward or backward translation)*: tighten the ceiling to mean fill ≲ **2–3%**, any single frame ≲ **5%**. The 4–8% band that looks "plausible" in a pan-only clip is almost certainly leaked near-field parallax in a dolly clip; shipping it costs more IoU than shipping those frames empty. Escalate in this order: enable border suppression (if off), switch to full 6-DOF affine (if using partial), switch to the **biquadratic** flow model (see the code above), tighten the detection `K` to ≥4 and the floor to ≥3 px, enable the temporal-persistence gate, apply the component-shaping guard (compactness + interior + size), raise `min_area` by ~2×, prefer intersection over union in the two-sided fusion. Re-check the floor afterwards — the goal is a mean fill in roughly the **0.5–2.5%** band for dolly-forward urban / walking scenes.

A good heuristic: a realistic small-to-medium moving object (pedestrian, vehicle, bike at wide FOV) occupies ~0.2–4% of the frame. Scenes typically contain 0–2 such objects at a time (crowd shots are rarer than they feel). So a believable per-frame fill distribution under a Dolly label is heavy around 0.3–2%, with the occasional outlier up to ~4% when an object is close. Flat 5–8% across many frames of a dolly-in walking shot is parallax, not objects — the IoU cost of shipping it almost always exceeds the recall it preserves.

> **Visual-inspection rule.** When you visually inspect a mask overlay before shipping, name the moving object you expect the mask to cover. Parked vans, hanging T-shirts / stall items, awnings, foliage, store signs and street furniture are *static* — if those are all that's highlighted, the mask is leakage even when the fill percentage looks "within band", and the better ship is either (a) a mask trimmed to only the moving object(s) via the shape+interior gate, or (b) an empty mask for that frame. Do not justify shipping a pretty-looking parallax blob by citing the sanity-window numbers alone.

# Self-check
- [ ] Masks produced for every sampled frame `k` in `0..n_samples-1`; keys match sampled indices.
- [ ] `shape` stored as `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`.
- [ ] Border fill not treated as foreground; threshold stats computed on valid (eroded) region only (Method A), or flow residual used (Method B).
- [ ] For scenes with notable Dolly or wide-FOV translation, Method B (flow residual) is used instead of raw image differencing.
- [ ] Global flow model is at least 6-DOF affine (`estimateAffine2D`) under any forward-translation; a **biquadratic (12-param) model fit with soft IRLS** is preferred whenever a Dolly label is present. `estimateAffinePartial2D` only for near-planar scenes.
- [ ] Border suppression applied to the residual before thresholding when a Dolly label is present (widen to 6–8% when the mean flow magnitude is non-trivial).
- [ ] Threshold defaults scale with the egomotion label mix: `K≈3.0, floor≈2.0` for pan/tilt-only clips; `K≈4.0, floor≈3.0` under any Dolly label with strong mean flow magnitude.
- [ ] Per-frame precision guard trips at ~4% fill under a Dolly label (vs ~8% otherwise); **retries tighter, then runs the component-shaping guard (compact + interior + size) with a higher shape bar (≈0.25), and — under a Dolly label — falls through to an empty mask rather than shipping an unverified blob**.
- [ ] Morphology order is small-open then larger-close (then optional small dilate); not the reverse.
- [ ] Two-sided (prev/next) residual fused for interior frames when feasible; **intersection**, not union, is used when `scene_has_dolly` and mean flow magnitude is non-trivial.
- [ ] Temporal-persistence gate applied for roughly-monotonic camera motion: pixels "on" in >~60% of frames are image-anchored clutter and are masked out.
- [ ] Frame 0 mask derived from the forward (0→1) flow, not left empty by default.
- [ ] Sanity window verified against the label-mix-dependent ceiling: mean fill ≲ ~2.5% under a Dolly label, ≲ ~4% for ordinary pan/tilt scenes; no single Dolly frame ships above ~5% without a named, visually-identifiable moving object.
- [ ] Visual sanity check: when overlaid, every retained component plausibly corresponds to a named moving object (person, vehicle, bike, animal); static-but-near clutter (parked vans, awnings, stall items, foliage, signs) is excluded.
- [ ] CSR `indices` and `indptr` dtypes are integer; `indices` stays within `[0, W)`.
