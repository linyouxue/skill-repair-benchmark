---
name: egomotion-estimation
description: "Estimate camera egomotion from sampled frames (robust global motion + dynamic-aware fitting) and emit half-open sample-index intervals."
---

# When to use
- You need to classify camera motion (**Stay / Dolly / Pan / Tilt / Roll**) from a video.
- The scene may contain **dynamic foreground objects**; your egomotion estimate must be dominated by **background** motion.

# Key conventions (avoid common off-by-one bugs)
These tasks typically want labels in **sample-index space**.

- Let `S` be the number of sampled frames.
- JSON keys `"{start}->{end}"` are **half-open ranges** on **sample indices**:
  - `0 <= start < end <= S`
  - `"0->1"` labels sampled frame 0 only.

## Mapping motion estimates to sample indices
If you estimate motion between consecutive sampled frames `i -> i+1`:
- Assign that motion label to **sample index `i`** (it describes the segment starting at `i`).
- Decide how to label the last sample index `S-1`:
  - common: repeat `label[S-2]` when `S>1` (or use `Stay` when `S==1`).

# Core idea: dynamic-object-aware global motion
A frequent failure mode is that RANSAC locks onto a large moving object and treats it as “camera motion”.
Mitigations that generalize well:

1) **Use robust statistics and enforce spatial coverage**
- Don’t judge a model only by inlier count; also require that inliers are spread across the image (background is global, a moving object is often local).

2) **Iterate: estimate motion → find dynamic regions → re-estimate motion**
- Even a crude first-pass dynamic mask helps remove foreground before refining the global transform.

# Workflow (recommended)
1) **Sample frames** at the target FPS and work in **sample-index space** (see `sampling-and-indexing`).
2) For each consecutive pair `(i, i+1)`:
   - Estimate a **global motion model** dominated by background.
   - Extract motion features (translation / zoom / roll).
3) **Temporal smoothing** on features or labels.
4) **Compress** per-index labels into half-open `start->end` intervals covering `[0, S)`.

# Global motion estimation options
## Option A (often strongest): dense optical-flow + robust parametric fit
This is usually more stable than raw affine scale from sparse matches.

### Important: translation-only baseline (prevents overfitting)
A low-DOF zoom/roll model can still overfit parallax or dynamic objects. A reusable safeguard is to fit:
1) **translation-only** `(tx, ty)`
2) **translation + zoom (+ roll)** `(tx, ty, k, wcoef)`

Then only trust the extra DOFs if they **materially reduce** robust residuals (e.g., median or trimmed-mean residual) on presumed-background pixels.

- Compute dense flow `flow(x,y) = (u,v)` from `frame[i]` → `frame[i+1]` on a **downsampled** grid.
- Fit a low-DOF global model to flow using robust regression / trimmed statistics.

A simple, effective basis:
- translation: `(tx, ty)`
- zoom (dolly): `k * (x-cx, y-cy)`
- roll: `w * (-(y-cy), (x-cx))`

You can estimate `tx,ty,k,w` with medians (robust) while ignoring the unstable center region.

### Extra robustness: coverage-aware medians (helps dynamic scenes)
Dense-flow fits can still be biased if a large moving object dominates a region. A simple reusable trick:
- split the flow grid into a coarse `G×G` set of cells (e.g. `4×4`)
- compute per-cell medians of `u` and `v` (and of the zoom/roll projections)
- take the median over cells (optionally requiring at least `K` populated cells)

This enforces spatial coverage without needing a full RANSAC implementation.

## Option B: sparse features + RANSAC affine/homography (with coverage checks)
- Track features (GFTT + LK) or match ORB.
- Use RANSAC to estimate `estimateAffinePartial2D` (or homography).
- **Reject/redo** if:
  - too few inliers,
  - reprojection residual is high,
  - inliers occupy only a small portion of image area.

Coverage heuristic example:
- partition the image into a `4×4` grid; require inliers in ≥ `K` distinct cells.

# Motion classification (camera-motion labels)
## Direction conventions (critical)
Assuming your motion is estimated as **image motion** from `i -> i+1` (how pixels/points shift in the image):
- image shifts **right** ⇒ camera pans **left**
- image shifts **left**  ⇒ camera pans **right**
- image shifts **down**  ⇒ camera tilts **up**
- image shifts **up**    ⇒ camera tilts **down**

## Disambiguate Dolly/Roll vs Pan/Tilt (avoid spurious Dolly/Roll)
Dense-flow fits can return a non-zero zoom/roll coefficient even when the true camera motion is mostly pan/tilt (e.g., yaw/pitch rotation, perspective/parallax, or a large dynamic foreground object biasing the fit). A classic pitfall is:
- a yaw/pitch rotation produces a flow field whose magnitude varies with position
- after subtracting the median translation, the residual can show left/right sign changes that *look* “zoom-like”

Before committing to **Dolly** or **Roll**, gate them with **multiple** pieces of evidence (do not rely on a single heuristic):

1) **Model-selection by residual reduction (required)**
Fit translation-only vs translation+zoom(+roll). Keep extra DOFs only if they *materially* reduce a robust residual (median / trimmed mean) relative to the residual noise scale (MAD).

2) **Radial/tangential projection check (strong)**
After subtracting `(tx, ty)`, project flow onto:
- radial direction `(x, y)`  → zoom signal
- tangential direction `(-y, x)` → roll signal
On a coarse grid (e.g., 4×4), require:
- for Dolly: radial medians have a consistent sign across many cells and tangential energy is small
- for Roll: tangential medians have a consistent sign across many cells and radial energy is small

3) **Sign-structure sanity (fast)**
If you still use the left/right & top/bottom sign-flip test, make it *strict* for Dolly:
- require **both** horizontal and vertical flips (not just one), and require non-trivial magnitude vs noise

4) **Spatial coverage**
Ensure the supporting pixels/cells are spread across the image; if the “evidence” lives in a small region, it is likely a moving object.

If any gate fails, **zero out** `k` and/or `wcoef` for classification and fall back to Pan/Tilt using `(tx, ty)` (or `Stay` if translation is also below threshold). When uncertain, prefer Pan/Tilt over Dolly/Roll rather than emitting spurious Dolly/Roll for an entire clip.

## Prefer “dominant component” scoring (avoid fixed priority)
A common mistake is classifying “Dolly” whenever the zoom/scale term is slightly non-zero.
Instead:
- compute comparable magnitudes for translation / zoom / roll on the **same units**
- pick the **largest** one that exceeds a noise-adaptive threshold

### Make zoom/roll magnitudes comparable to translation
If your global-flow model uses coefficients like `k` (zoom) and `w` (roll) where the actual pixel motion grows with distance from the center, compare them in **pixel units** using a representative radius:
- `rmax ≈ hypot((W-1)/2, (H-1)/2)` (or a percentile radius)
- `zoom_px ≈ |k| * rmax`
- `roll_px ≈ |w| * rmax`
- `trans_px ≈ max(|tx|, |ty|)`

Then select the dominant component by these comparable magnitudes (after smoothing), not by raw coefficient size.

(Alternative) If you prefer normalized magnitudes, that’s fine — just ensure **all components are comparable**. For zoom/roll coefficients whose effect scales with radius, convert them to an equivalent pixel magnitude (e.g., multiply by a representative radius) before comparing.

### Thresholding (avoid instance-specific constants)
Avoid hard-coding thresholds tied to one resolution/video.
Prefer thresholds derived from a robust noise estimate **on the same grid/units as your motion magnitudes**:
- fit the global model
- compute flow residual magnitudes on presumed-background pixels
- estimate `sigma ≈ 1.4826 * MAD(resid)`
- choose a conservative base threshold in pixels, e.g. `base_px = max(eps_px, c * sigma)`
- treat a motion component as “present” only if its pixel-magnitude is well above `base_px`

### Add a “degenerate constant label” sanity check
If your per-pair labels collapse to a single label for the entire clip (especially Dolly/Roll), it may indicate model bias. Re-check:
- pan/tilt direction convention (image motion vs camera motion)
- whether zoom/roll is being selected without passing the evidence checks above
- whether dynamic objects dominate your global fit (insufficient spatial coverage)

This prevents a small zoom/roll coefficient from dominating when overall motion is near-zero.

# Code sketch (dense-flow basis fit + dominant label)
```python
import numpy as np
import cv2

ALLOWED = {
  "Stay","Dolly In","Dolly Out","Pan Left","Pan Right",
  "Tilt Up","Tilt Down","Roll Left","Roll Right",
}

def robust_mad(x: np.ndarray) -> float:
    x = x.astype(np.float32).ravel()
    if x.size == 0:
        return 0.0
    med = float(np.median(x))
    return float(np.median(np.abs(x - med)))

def fit_translation_only(flow, valid=None):
    """Fit translation-only (tx, ty) to dense flow on a grid (robust)."""
    u = flow[..., 0].astype(np.float32)
    v = flow[..., 1].astype(np.float32)
    if valid is None:
        valid = np.ones(u.shape, dtype=bool)
    tx = float(np.median(u[valid]))
    ty = float(np.median(v[valid]))
    return tx, ty

def fit_global_flow(flow, valid=None):
    """Fit translation + zoom + roll to flow on a (h,w,2) grid."""
    h, w = flow.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    x = (xx - cx).astype(np.float32)
    y = (yy - cy).astype(np.float32)

    u = flow[..., 0].astype(np.float32)
    v = flow[..., 1].astype(np.float32)

    if valid is None:
        valid = np.ones((h, w), dtype=bool)

    # ignore tiny radius near center (unstable for zoom/roll fits)
    r2 = x * x + y * y
    ok = valid & (r2 > 25.0)

    # robust translation
    tx = float(np.median(u[valid]))
    ty = float(np.median(v[valid]))

    # remove translation before fitting zoom/roll
    u0 = u - tx
    v0 = v - ty

    # zoom coefficient k: projection onto radial direction
    # (u0,v0) · (x,y) / ||(x,y)||^2
    k = float(np.median(((u0 * x + v0 * y) / r2)[ok])) if np.any(ok) else 0.0

    # roll coefficient w: projection onto tangential direction
    # (u0,v0) · (-y,x) / ||(x,y)||^2
    wcoef = float(np.median(((u0 * (-y) + v0 * x) / r2)[ok])) if np.any(ok) else 0.0

    return tx, ty, k, wcoef

def classify_from_components(tx, ty, k, wcoef, H, W, resid_sigma,
                             zoom_ok: bool = True, roll_ok: bool = True):
    """Classify motion from fitted components.

    zoom_ok / roll_ok are evidence gates: set them False when zoom/roll does not
    pass your validation checks (residual reduction, sign-flip structure, etc.).
    """

    # Compare components in *pixel units* on the flow grid.
    # Translation is already in pixels; zoom/roll coefficients need a radius.
    rmax = ( (max(1.0, W) - 1.0) / 2.0 )**2 + ( (max(1.0, H) - 1.0) / 2.0 )**2
    rmax = rmax**0.5

    trans_px = max(abs(tx), abs(ty))
    zoom_px = abs(k) * rmax if zoom_ok else 0.0
    roll_px = abs(wcoef) * rmax if roll_ok else 0.0

    mags = {"trans": trans_px, "zoom": zoom_px, "roll": roll_px}
    kind = max(mags, key=mags.get)
    max_mag = float(mags[kind])

    # Residual sigma is a noise proxy (pixels). Use a conservative floor.
    base_px = max(0.15, 2.5 * float(resid_sigma))

    if max_mag < base_px:
        return ["Stay"]

    if kind == "zoom":
        return ["Dolly In" if k > 0 else "Dolly Out"]
    if kind == "roll":
        return ["Roll Right" if wcoef > 0 else "Roll Left"]

    # Translation -> pan/tilt using IMAGE motion direction convention.
    if abs(tx) >= abs(ty):
        return ["Pan Left" if tx > 0 else "Pan Right"]
    return ["Tilt Up" if ty > 0 else "Tilt Down"]
```

# Self-check
- [ ] If tracking/flow fails, fall back to identity motion and emit `Stay` (never emit an empty label list).
- [ ] Direction conventions are correct for your chosen “image-motion” definition.
- [ ] If Dolly/Roll is selected, it passes at least one evidence check (sign-flip structure and/or residual reduction vs translation-only).
- [ ] Avoid instance-specific thresholds; prefer normalized magnitudes + robust noise-based thresholds.
- [ ] Default output is **one** label per interval unless the prompt explicitly requests multi-label.
- [ ] Intervals are half-open on **sample indices** and partition `[0, S)` with no gaps/overlaps; last interval ends at `S`.
- [ ] No off-by-one: if motion is computed for `i -> i+1`, attach it to sample index `i` and handle `S-1` explicitly.
