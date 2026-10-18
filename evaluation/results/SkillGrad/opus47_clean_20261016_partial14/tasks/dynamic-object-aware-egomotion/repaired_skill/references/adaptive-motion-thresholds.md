# Adaptive motion thresholds — MAD-based, physical floor first

Trigger: egomotion-estimation's "Adaptive thresholding" pointer fires when
you need per-sequence thresholds (non-trivial sampling stride, unknown fps,
your initial labels contradict the obvious scene prior, the MAD-saturation
check fires, or the fraction-non-Stay > 0.90 red flag fires at
post-classification).

## Role split (critical)

A threshold has two independent terms. Confusing their roles is the single
most common calibration bug:

| Term  | What it measures               | Stride-aware? | Set how                           |
|-------|--------------------------------|---------------|-----------------------------------|
| MAD   | sampled-pair noise amplitude   | Yes — automatically, because the signal is already between sampled pairs | measured from the data: `K * MAD(signal)` with K ≈ 3 |
| FLOOR | absolute static-scene tolerance | **No — fixed physical constant** | `TRANS_FLOOR_PX ≈ 1–2`, `ROT_FLOOR_RAD ≈ 0.004`, `SCALE_FLOOR_REL ≈ 0.005` |

**Never multiply the floor by sampling stride.** The MAD term absorbs
stride automatically; the floor is a small absolute number that only
matters when the scene is nearly static (MAD ≈ 0).

**MAD assumes a quiescent noise band.** MAD breaks a second way on
continuous-motion scenes (walking POV at near-constant velocity, panning
tripod) where almost every pair carries similar motion magnitude — MAD
measures the signal itself, not noise. `K × MAD` then sits just above
the signal and classifies the whole sequence as `Stay`. See Phase 2 for
the saturation diagnostic + fallback (and the mirror-failure hazard).

## Phase 1 — Collect per-pair signals across the full sampled sequence

```python
import cv2, numpy as np

def pair_signal(prev_gray, curr_gray, min_pts=30):
    pts0 = cv2.goodFeaturesToTrack(prev_gray, maxCorners=400,
                                   qualityLevel=0.01, minDistance=8)
    if pts0 is None or len(pts0) < min_pts:
        return None
    pts1, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, pts0, None)
    good0 = pts0[st.ravel() == 1]; good1 = pts1[st.ravel() == 1]
    if len(good0) < min_pts:
        return None
    M, inl = cv2.estimateAffinePartial2D(good0, good1, method=cv2.RANSAC)
    if M is None:
        return None
    dx, dy = M[0, 2], M[1, 2]
    rot = np.arctan2(M[1, 0], M[0, 0])
    scale = np.hypot(M[0, 0], M[1, 0])
    pred = (M[:, :2] @ good0.reshape(-1, 2).T).T + M[:, 2]
    resid = np.linalg.norm(good1.reshape(-1, 2) - pred, axis=1)
    return dict(M=M, dx=dx, dy=dy, rot=rot, scale=scale,
                resid_med=float(np.median(resid)),
                resid_mad=float(np.median(np.abs(resid - np.median(resid)))))

sigs = [pair_signal(a, b) for a, b in zip(sampled_grays[:-1], sampled_grays[1:])]
sigs = [s for s in sigs if s is not None]
dxs    = np.array([s["dx"]    for s in sigs])
dys    = np.array([s["dy"]    for s in sigs])
rots   = np.array([s["rot"]   for s in sigs])
scales = np.array([s["scale"] for s in sigs])
```

Branch — too few valid pairs:
- If `len(sigs) < 5`, MAD is unstable. Keep the FIXED floors below as the
  thresholds (do NOT substitute `floor * stride`). Log a warning so the
  semantic sanity check knows to be stricter.

## Phase 2 — MAD + fixed floor, with saturation fallback (physical-floor first)

```python
def mad(x):
    return 1.4826 * np.median(np.abs(x - np.median(x)))

# Fixed absolute floors — DO NOT multiply by sampling stride
TRANS_FLOOR_PX  = 1.5
ROT_FLOOR_RAD   = np.deg2rad(0.25)    # ~0.0044 rad
SCALE_FLOOR_REL = 0.005
K = 3.0

# Default: K × MAD above the floor.
th_trans = max(TRANS_FLOOR_PX,  K * max(mad(dxs), mad(dys)))
th_rot   = max(ROT_FLOOR_RAD,   K * mad(rots))
th_scale = max(SCALE_FLOOR_REL, K * mad(scales - 1.0))
```

### MAD-saturation diagnostic

```python
def mad_saturated(signal, k=K):
    """True when the signal median exceeds K×MAD — i.e. the signal is
    larger than what MAD would consider noise. On continuous-motion
    scenes, MAD is measuring the signal, not quiescent noise."""
    s = np.asarray(signal)
    return np.median(np.abs(s)) > k * mad(s)
```

### Mirror-failure hazard

The naive fallback `0.25 × median(|signal|)` is **itself a data-driven
threshold on the same saturated distribution**. On a scene with large
consistent motion (walking POV, dashcam), it drops to a small fraction
of the motion and classifies ~every pair as non-Stay — the mirror of
the MAD-saturated-high failure it was meant to fix. (iter_3 shipped
dominant-`Stay`; iter_4 applied the fallback and shipped dominant-
non-Stay with 17/18 pairs flagged. Same scene type, mirror-image
failure.)

### Fallback ordering

```python
# Translation axis
if mad_saturated(dxs) or mad_saturated(dys):

    # ---- First choice: PHYSICAL FLOOR ----
    # The fixed TRANS_FLOOR_PX is a physical minimum-resolvable
    # translation; on a scene where the real motion is well above the
    # floor, this cleanly separates Stay from non-Stay. If sampling
    # stride is large enough that per-pair motion resolution matters,
    # a stride-informed physical floor (~1 px per 8 raw frames) is
    # the right scale. This is NOT a stride-scaled floor — it's a
    # physical quantity happens to be a function of stride.
    th_trans = max(TRANS_FLOOR_PX, stride / 8.0)
    print(f"adaptive: trans MAD saturated → physical floor "
          f"th_trans={th_trans:.2f} (= max(TRANS_FLOOR_PX, stride/8))")

    # ---- Second choice: quiet-mode noise reference (if bimodal) ----
    # Only when the signal is clearly bimodal with a quiet mode and a
    # motion mode. Detect: lower quartile is much smaller than upper
    # quartile → the signal has a quiet population.
    combined = np.r_[np.abs(dxs), np.abs(dys)]
    q25, q75 = np.percentile(combined, [25, 75])
    bimodal = q25 < 0.3 * q75
    if bimodal:
        th_trans = max(TRANS_FLOOR_PX, 3.0 * q25)
        print(f"adaptive: bimodal signal → quiet-mode floor "
              f"th_trans={th_trans:.2f} (= max(FLOOR, 3*q25))")

    # ---- Last resort: 0.25 * median(|signal|) ----
    # Diagnostic logging only. Do NOT ship a label distribution from
    # this fallback without separately clearing the "fraction non-Stay
    # > 0.90" red flag (see Phase 3). On a scene with large consistent
    # motion, this fallback over-triggers the mirror failure.
    last_resort = 0.25 * np.median(combined)
    print(f"adaptive: diagnostic — 0.25*median|signal|={last_resort:.2f} "
          f"(NOT shipped unless physical floor fails downstream red flags)")

# Rotation axis — same ordering
if mad_saturated(rots):
    th_rot = max(ROT_FLOOR_RAD, np.deg2rad(0.5) * (stride / 8.0))
    print(f"adaptive: rot MAD saturated → physical floor th_rot={th_rot:.4f}")

# Scale axis — same ordering
if mad_saturated(scales - 1.0):
    th_scale = max(SCALE_FLOOR_REL, 0.001 * stride)
    print(f"adaptive: scale MAD saturated → physical floor th_scale={th_scale:.4f}")
```

## Phase 3 — Classify, then audit the resulting distribution

```python
SCENE_PRIORS = {
    "walking_pov":  {"expected_dominant": "Dolly In",
                     "forbid_dominant":   {"Stay"}},
    "tripod":       {"expected_dominant": "Stay",
                     "forbid_dominant":   {"Dolly In", "Dolly Out"}},
    "dashcam":      {"expected_dominant": "Dolly In",
                     "forbid_dominant":   {"Stay"}},
}

labels_per_pair = classify(sigs, th_trans, th_rot, th_scale)
flat = [l for ls in labels_per_pair for l in ls]
dom = max(set(flat), key=flat.count) if flat else None

# Fraction-non-Stay red flag — fires when the saturation fallback
# over-triggered (threshold too low).
frac_non_stay = sum(ls != ["Stay"] for ls in labels_per_pair) / max(1, len(labels_per_pair))

# Dominant direction fraction (any single non-Stay direction)
dominant_dir_frac = 0.0
for d in ("Pan Left","Pan Right","Tilt Up","Tilt Down","Dolly In","Dolly Out"):
    f = sum(d in ls for ls in labels_per_pair) / max(1, len(labels_per_pair))
    dominant_dir_frac = max(dominant_dir_frac, f)
```

### Verification + corrective action — mirror-failure branches

```python
# Mode 1: Dominant Stay on a motion-prior scene (iter_3 symptom).
# Cause: MAD saturated high; thresholds above the signal.
if dom == "Stay" and SCENE_PRIORS[scene]["expected_dominant"] != "Stay":
    # Apply Phase-2 physical-floor fallback (NOT 0.25*median) and re-classify.
    raise AssertionError(
        f"dominant Stay on motion-prior scene; MAD likely saturated. "
        f"Apply physical floor max(TRANS_FLOOR_PX, stride/8) and re-run.")

# Mode 2: frac_non_stay > 0.90 (iter_4 symptom).
# Cause: fallback threshold too low — mirror of Mode 1.
if frac_non_stay > 0.90:
    # Switch to physical floor if you were using 0.25*median; or raise
    # the physical floor if stride/8 is still too permissive.
    raise AssertionError(
        f"frac_non_stay={frac_non_stay:.2f} > 0.90; fallback likely "
        f"over-triggered. Fix: switch to max(TRANS_FLOOR_PX, stride/8); "
        f"do NOT tune to clear this red flag. Re-classify.")

# Mode 3: One direction label dominates > 60% with varied-motion prior.
# Cause: inverted polarity on that axis — NOT a threshold problem.
if dominant_dir_frac > 0.60:
    # Re-run the external-anchor step (references/sign-convention-selftest.md
    # Layer A); do NOT retune thresholds to clear this.
    raise AssertionError(
        f"dominant_dir_frac={dominant_dir_frac:.2f} > 0.60; polarity "
        f"likely inverted. Re-run external-anchor Layer A on a different "
        f"real pair; do NOT retune thresholds.")

# Mode 4: Floor dominates despite visible motion (floor stride-scaled by mistake).
dominated_by_floor = (th_trans == TRANS_FLOOR_PX and
                      K * max(mad(dxs), mad(dys)) < 0.5 * TRANS_FLOOR_PX)
if dominated_by_floor and max(np.abs(dxs).max(), np.abs(dys).max()) > TRANS_FLOOR_PX:
    raise AssertionError("floor dominates despite motion present; review calibration "
                         "(did you multiply the floor by stride?)")

# Mode 5: Oscillating multi-label every sample — thresholds too small.
# Raise K to 4, or inspect MAD input for outliers.
```

## Phase 4 — Temporal smoothing (asymmetric)

A mode/median filter that treats `Stay` and non-Stay symmetrically is a
false-negative trap: at large stride a single sampled `Pan` between two
`Pan`s is a real transition recorded once, not flicker.

```python
def smooth_labels(seq):
    out = [list(s) for s in seq]
    for i in range(1, len(seq) - 1):
        prev_set, this_set, next_set = set(seq[i-1]), set(seq[i]), set(seq[i+1])
        # Only suppress isolated non-Stay between two Stays
        if this_set != {"Stay"} and prev_set == {"Stay"} and next_set == {"Stay"}:
            out[i] = ["Stay"]
    return out
```

Verification + corrective action on smoothing:
```python
def find_bad_sandwiches(seq):
    bad = []
    for i in range(1, len(seq) - 1):
        prev_set, this_set, next_set = set(seq[i-1]), set(seq[i]), set(seq[i+1])
        # X / Stay / X with X != Stay survived — real transition was eaten
        if this_set == {"Stay"} and prev_set == next_set and prev_set != {"Stay"}:
            bad.append(i)
    return bad

bad = find_bad_sandwiches(smoothed)
if bad:
    # Smoothing window is too aggressive OR th_trans/th_rot/th_scale are
    # too large on the middle pair. Drop smoothing, then re-check th_* vs
    # the middle pair's signal before shipping.
    raise AssertionError(f"X/Stay/X sandwich at indices {bad}; reclassify without smoothing")
```
