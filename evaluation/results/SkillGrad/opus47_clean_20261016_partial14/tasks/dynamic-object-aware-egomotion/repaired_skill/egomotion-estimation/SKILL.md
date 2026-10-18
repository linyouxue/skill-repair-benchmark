---
name: egomotion-estimation
description: "Estimate camera motion with optical flow + affine/homography, allow multi-label per frame, calibrate thresholds adaptively, anchor sign convention externally."
---

# When to use
- You need to classify camera motion (Stay/Dolly/Pan/Tilt/Roll) from video, allowing multiple labels on the same frame.

# Workflow
1) **Feature tracking**: `goodFeaturesToTrack(prev_gray)` + `calcOpticalFlowPyrLK`; drop if too few points.
2) **Robust transform**: `estimateAffinePartial2D(src=prev_pts, dst=curr_pts, method=RANSAC)` — `M` maps **prev → curr**. The src/dst ordering decides the sign of every label; see "Sign-convention external anchor" below.
3) **Sign-convention external anchor** (hard gate, see section below): the 4-case synthetic self-test is **necessary but tautological** (classifier branch and assertion both read the pinned table). Anchor correctness on a **real sampled pair**: log observed feature displacement + a one-line prose description of what the camera is actually doing, and verify the classifier's emitted label on that pair matches the prose. Only then run self-consistency.
4) **Calibrate thresholds adaptively** (see "Adaptive thresholding"): collect `(dx, dy, rot, scale)` across the full sampled sequence first, then set `th_trans / th_rot / th_scale` from the empirical noise floor — never with hardcoded per-pixel values. Check for MAD-saturation; prefer the physical floor over any data-driven fallback.
5) **Classify + allow multi-label**: if scale and translate both exceed their thresholds, emit Dolly + Pan; rotation independent for Roll. Polarities keyed to the pinned convention table below.
6) **Temporal smoothing** (see "Temporal smoothing"): only suppress isolated non-Stay labels surrounded by `Stay`; never collapse a non-Stay label whose both neighbors carry the same non-Stay label.
7) **Pair→interval emission**: emit one label per sampled pair as an interval key `"sample_ids[i]->sample_ids[i+1]"` directly (default). See `sampling-and-indexing`'s "Pair-to-frame label alignment" before choosing per-frame assignment instead.
8) **Interval compression**: merge consecutive intervals with identical label sets into one `start->end` key.
9) **Dominant-direction red flag**: after classifying all pairs, if any single non-Stay direction label dominates >60% of pairs, or if fraction-non-Stay > 0.90 on a scene with varied motion, suspect inverted polarity or threshold mis-calibration — re-anchor via step 3 before shipping.

# Pinned Pan/Dolly/Tilt convention — keyed to `src=prev_pts, dst=curr_pts`

| `M` value       | Content motion (curr vs prev)       | Camera motion         | Label        |
|-----------------|--------------------------------------|-----------------------|--------------|
| `tx > 0`        | content shifted **right**            | camera panned **left**  | `Pan Left`   |
| `tx < 0`        | content shifted **left**             | camera panned **right** | `Pan Right`  |
| `ty > 0`        | content shifted **down**             | camera tilted **up**    | `Tilt Up`    |
| `ty < 0`        | content shifted **up**               | camera tilted **down**  | `Tilt Down`  |
| `scale > 1`     | content **larger**                   | camera moved **forward**  | `Dolly In`  |
| `scale < 1`     | content **smaller**                  | camera moved **backward** | `Dolly Out` |

**Warning — tautology hazard.** This table assumes `src=prev, dst=curr`
AND the standard image coordinate frame (y-down). A self-test derived
from this table (code reads the table to classify; assertion reads the
table to pin the expected label) cannot catch an inverted table. The
table must be **externally anchored** per real pair before trust — see
the next section.

# Decision sketch
```python
labels=[]
for each sampled pair i:
    dx, dy = M[0,2], M[1,2]
    rot    = np.arctan2(M[1,0], M[0,0])
    scale  = np.hypot(M[0,0], M[1,0])
    lbl=[]
    if abs(scale-1)>th_scale: lbl.append("Dolly In" if scale>1 else "Dolly Out")
    if abs(rot)>th_rot:       lbl.append("Roll Right" if rot>0 else "Roll Left")
    if abs(dx)>th_trans and abs(dx)>=abs(dy):
        lbl.append("Pan Left" if dx>0 else "Pan Right")
    if abs(dy)>th_trans and abs(dy)>abs(dx):
        lbl.append("Tilt Up" if dy>0 else "Tilt Down")
    if not lbl: lbl.append("Stay")
    labels.append(lbl)
```

# Sign-convention external anchor (hard gate)

The 4-case synthetic self-test (`+roll axis=1`, `-roll axis=1`,
`+roll axis=0`, `upscale`) is **a self-consistency check, not a
correctness check**: the classifier branch and the assertion both derive
from the same pinned table. If the pinned table is inverted relative to
the grader, every self-test case still passes while every real label
flips. The gate therefore has two layers:

**Layer A — External anchor on a real sampled pair (correctness).** Load
`prev = frames[sample_ids[0]]` and `curr = frames[sample_ids[1]]`. Pick
2–3 trackable features visible in both frames. Log observed displacement
and a one-line prose description of what the camera is doing. The
classifier's emitted label on this pair must match the prose; if it
does not, flip the polarity branch on the disagreeing axis (do NOT
change the prose).

```python
# Minimal external-anchor sketch — specifics in references/sign-convention-selftest.md
pts0, pts1 = track_features(prev_gray, curr_gray)   # 2-3 features
dx_obs = float(np.median(pts1[:, 0] - pts0[:, 0]))
dy_obs = float(np.median(pts1[:, 1] - pts0[:, 1]))
# One-line prose description based on observed displacement direction:
# e.g. "content shifts LEFT across frame — camera is panning RIGHT"
# e.g. "content EXPANDS from center — camera is dollying IN"
prose = describe_camera_motion(dx_obs, dy_obs, scale_obs)
print(f"external-anchor: dx_obs={dx_obs:+.2f} dy_obs={dy_obs:+.2f} prose='{prose}'")

M = estimate_from_pair(prev_gray, curr_gray)
emitted = classify_from_M(M)
# Correctness assertion: the emitted label on this real pair must match
# the prose. A tautological self-test cannot replace this check.
assert label_matches_prose(emitted, prose), (
    f"external anchor FAILED: emitted={emitted}, prose='{prose}'. "
    f"Flip classifier polarity on the disagreeing axis (NOT the prose).")
print("external-anchor:pass")
```

**Layer B — Self-consistency check (4-case synthetic gate).** Only after
Layer A passes, run the 4-case synthetic test to confirm every emitted
axis has an in-sync polarity branch.

```python
# Case 1-4: see references/sign-convention-selftest.md. Must emit all four
# pass tokens: sign-test:pan-left:pass, pan-right:pass, tilt-up:pass, dolly-in:pass.
```

**Dominant-direction red flag (post-classification).** After classifying
all pairs, if any single non-Stay direction label (`Pan Right`, `Pan
Left`, `Tilt Up`, `Tilt Down`, `Dolly In`, `Dolly Out`) dominates >60%
of pairs on a scene prior with variable motion, OR if the fraction of
non-Stay pairs is >0.90 (unusually high — suggests threshold mis-
calibration or MAD-saturation fallback over-triggered), suspect
inverted polarity on the dominant axis or a tuned threshold. Re-run
Layer A on a different pair; do NOT ship a dominant-direction
distribution without re-anchoring.

Read `references/sign-convention-selftest.md` for the full external
anchor + 4-case self-consistency gate, the pinned convention table, and
the branched corrective action when the external anchor disagrees with
the self-test. Skip only when the caller supplies a reference label
pair `(frame_i, frame_j) → label` from the task spec AND the classifier
passes it (strongest anchor).

# Adaptive thresholding
A threshold has two independent terms. Keep their roles separate:

- **MAD term** — measured on the sampled-pair signal
  (`dx, dy, rot, scale-1`). This is **already stride-aware** because the
  signal itself is measured between sampled pairs: at larger stride, both
  signal and MAD grow together. Multiply MAD by a small constant `K≈3`.
- **FLOOR term** — a fixed absolute physical tolerance. **Never multiply
  the floor by sampling stride.**

```python
import numpy as np
def mad(x): return 1.4826 * np.median(np.abs(x - np.median(x)))

TRANS_FLOOR_PX  = 1.5                 # px, absolute — DO NOT scale by stride
ROT_FLOOR_RAD   = np.deg2rad(0.25)    # ≈ 0.004 rad — DO NOT scale by stride
SCALE_FLOOR_REL = 0.005               # relative — DO NOT scale by stride
K = 3.0

th_trans = max(TRANS_FLOOR_PX,  K * max(mad(dxs), mad(dys)))
th_rot   = max(ROT_FLOOR_RAD,   K * mad(rots))
th_scale = max(SCALE_FLOOR_REL, K * mad(scales - 1.0))
```

**MAD-saturation check (continuous-motion scenes).** On scenes where
almost every pair has similar motion magnitude, MAD measures the
*signal*, not noise — `K × MAD` sits just above the signal, flipping
real motion into `Stay`. Diagnostic: `median(|signal|) > K × MAD(signal)`.

**Fallback ordering (mirror-failure hazard).** The fallback itself can
over-trigger: `0.25 × median(|signal|)` is a data-driven threshold on
the same saturated distribution, so on a scene with large consistent
motion it drops to a small fraction of the motion and classifies
everything as non-Stay (iter_4 mirror of iter_3). Prefer the physical
floor; use `0.25 × median` only as a last resort.

```python
if mad_saturated(dxs) or mad_saturated(dys):
    # First choice: a physical floor, possibly stride-informed on a
    # minimum-resolvable-motion basis (not a stride-scaled floor).
    th_trans = max(TRANS_FLOOR_PX, stride / 8.0)
    print(f"th_trans: MAD saturated → physical floor {th_trans:.2f}")

    # Second choice (only if signal is clearly bimodal with a quiet mode):
    #   q25, q75 = np.percentile(|signal|, [25, 75])
    #   if q25 < 0.3 * q75:  # bimodal
    #       th_trans = max(TRANS_FLOOR_PX, 3 * q25)

    # Last resort: 0.25 * median(|signal|). Diagnostically log the value
    # but do NOT ship the resulting distribution without clearing the
    # "fraction non-Stay > 0.90" red flag (see Workflow step 9).
```

Decision rule: after setting `th_*`, project the resulting label
distribution. If fraction-non-Stay > 0.90 OR fraction-Stay > 0.95, the
threshold is on the wrong side of the signal — do NOT tune to clear the
red flag; re-run the MAD-saturation diagnostic and prefer the physical
floor. Scene prior mismatch (walking POV returning mostly `Stay`;
tripod returning big `Dolly`) is a related signal.

Read `references/adaptive-motion-thresholds.md` when thresholds must be
derived from the data (non-trivial sampling stride, unknown fps, scene
prior mismatch, MAD-saturation fires, or fraction-non-Stay > 0.90 red
flag). Skip when thresholds are supplied by the caller or the sequence
is < ~5 sampled pairs.

# Temporal smoothing
A width-W mode/median filter on the label stream is a false-negative trap
at large sampling strides: a single sampled transition can be a real
motion change, not flicker. Follow one rule:

- Suppress an isolated non-Stay label **only** when both neighbors are
  `Stay` (true flicker).
- **Never collapse** a non-Stay label whose both neighbors carry the same
  non-Stay label — that is a real transition recorded at a single sample.

```python
def smooth_labels(seq):
    out = [list(s) for s in seq]
    for i in range(1, len(seq) - 1):
        prev_set, this_set, next_set = set(seq[i-1]), set(seq[i]), set(seq[i+1])
        if this_set != {"Stay"} and prev_set == {"Stay"} and next_set == {"Stay"}:
            out[i] = ["Stay"]
    return out
```

Verification: after smoothing, scan for `X / Stay / X` sandwiches with
X ≠ Stay. If any survive, the smoothing window is too wide — drop
smoothing or re-run without the mode filter before shipping.

# Low-signal fallbacks
- Low texture/low light: increase feature count, use larger LK windows, and relax RANSAC settings.
- Too few inliers: fall back to the identity transform for that pair; never emit empty labels.

# Self-check
- [ ] `estimateAffinePartial2D` called as `src=prev_pts, dst=curr_pts` (M maps prev→curr).
- [ ] **External-anchor pass this run**: a real sampled pair was loaded, 2–3 features tracked, observed `(dx_obs, dy_obs)` logged with a one-line prose description of camera motion, and the classifier's emitted label on that pair matches the prose. Pass token `external-anchor:pass` present in-trace.
- [ ] **4-case self-consistency check executed**: all four pass tokens printed in-trace — `sign-test:pan-left:pass`, `sign-test:pan-right:pass`, `sign-test:tilt-up:pass`, `sign-test:dolly-in:pass`. (Self-consistency only; the external anchor is the correctness check.)
- [ ] Thresholds derived from the empirical `(dx,dy,rot,scale)` distribution; **floors are fixed absolute values, not multiplied by stride**.
- [ ] **MAD-saturation check performed**: if `median(|signal|) > K × MAD` on any axis, the physical floor (or `max(FLOOR, stride/8)`) was used; `0.25 × median(|signal|)` is a last resort only.
- [ ] **Dominant-direction red flag cleared**: no single non-Stay direction label dominates >60% of pairs; fraction-non-Stay ≤ 0.90. If flagged, re-anchored via external anchor before shipping.
- [ ] Label trajectory sanity-checked against the scene prior (walking POV → Dolly In dominant; tripod → Stay dominant).
- [ ] No `X / Stay / X` sandwich (X ≠ Stay) survives smoothing; no `Stay / Y / Stay` collapsed when Y's neighbors agree.
- [ ] Fallback to identity transform on failure; never emit empty labels.
- [ ] Multi-label allowed; no forced single label.
- [ ] Pair→interval alignment chosen explicitly per `sampling-and-indexing`; convention logged in-trace.
- [ ] Compressed intervals cover all sampled pairs; keys formatted correctly.

# Common pitfalls
- **Tautological self-test.** The 4-case synthetic self-test's classifier
  branch and assertion both derive from the same pinned table — the gate
  checks self-consistency, not correctness. If the pinned table is
  inverted relative to the grader, every case still passes while every
  real label flips. Anchor correctness on a **real sampled pair** with
  an observed-displacement + prose-description pair before trusting the
  self-test.
- **Data-driven fallback on a data-driven-saturated signal.** When MAD
  saturates on continuous motion, `0.25 × median(|signal|)` is itself
  a threshold measured on the same saturated distribution — it can
  over-trigger the mirror failure (threshold → too low → ~every pair
  non-Stay). Prefer a physical floor; always clear the fraction-non-Stay
  red flag after applying any saturation fallback.
- Scaling the FLOOR by sampling stride. MAD is already stride-aware; the
  floor is a fixed physical tolerance. Multiplying inflates the threshold
  enough to label real pans as `Stay`.
- Width-3 mode/median smoothing that collapses genuine transitions. Only
  suppress a non-Stay label when **both** neighbors are `Stay`; otherwise
  leave it alone.
- Attaching a pair-(i, i+1) label to a single sampled frame index with no
  documented contract. Default: emit per-interval, not per-frame. See
  `sampling-and-indexing` "Pair-to-frame label alignment" before deviating.
