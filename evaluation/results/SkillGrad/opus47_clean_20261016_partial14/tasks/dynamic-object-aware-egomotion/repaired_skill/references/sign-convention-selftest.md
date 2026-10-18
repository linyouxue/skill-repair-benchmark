# Sign-convention external anchor + 4-case self-consistency

Trigger: `egomotion-estimation`'s "Sign-convention external anchor" pointer
fires before any real-pair classification. The direction of a Pan / Tilt /
Dolly label flips with the `src`/`dst` ordering of
`cv2.estimateAffinePartial2D` and with the sign convention mapping
`(tx, ty, scale)` → label. **A 4-case synthetic self-test alone is a
tautology** — the classifier branch and the assertion both derive from
the same pinned table, so the test can never catch an inverted table. The
gate therefore has two layers:

- **Layer A — External anchor on a real sampled pair** (correctness
  check). Loads a real pair, tracks features, logs the observed
  displacement and a prose description of the actual camera motion, and
  verifies the classifier agrees with the prose. This is the only layer
  that can catch an inverted pinned table.
- **Layer B — 4-case self-consistency** (internal consistency check).
  Confirms every emitted axis has an in-sync polarity branch given the
  pinned table.

Layer A is **required**; Layer B alone is not sufficient. If the task
spec provides a reference `(frame_i, frame_j) → label` example, that
example overrides both layers (strongest anchor).

## Pinned convention (keyed to the actual API call)

For the pipeline the egomotion workflow prescribes:
```
goodFeaturesToTrack(prev_gray) → calcOpticalFlowPyrLK(prev, curr)
  → estimateAffinePartial2D(src=prev_pts, dst=curr_pts) → M
```
`M` maps `prev → curr`. For a pure translation of `(tx, ty)`:

| M value         | Meaning (image content)            | Camera motion   | Label         |
|-----------------|------------------------------------|-----------------|---------------|
| `tx > 0`        | content shifted **right** in curr   | camera panned **left**  | `Pan Left`   |
| `tx < 0`        | content shifted **left** in curr    | camera panned **right** | `Pan Right`  |
| `ty > 0`        | content shifted **down** in curr    | camera tilted **up**    | `Tilt Up`    |
| `ty < 0`        | content shifted **up** in curr      | camera tilted **down**  | `Tilt Down`  |
| `scale > 1`     | content **larger** in curr          | camera moved **forward** | `Dolly In`  |
| `scale < 1`     | content **smaller** in curr         | camera moved **backward**| `Dolly Out` |

**Warning.** This table assumes `src=prev, dst=curr` AND the standard
image coordinate frame (y-down). If `src/dst` are reversed, every row
flips. A self-test derived from this table (code reads the table to
classify; assertion reads the table to pin the expected label) **cannot
catch an inverted mapping** — do not derive the convention from a
comment and do not treat the 4-case gate as a correctness check. Run
Layer A below first.

## Layer A — External anchor on a real sampled pair (correctness)

```python
import cv2, numpy as np

def track_features_for_anchor(prev_gray, curr_gray, n_features=3):
    """Pick a handful of strong corners that survive LK; return matched
    (prev_pts, curr_pts) arrays of shape (k, 2)."""
    pts0 = cv2.goodFeaturesToTrack(prev_gray, maxCorners=200,
                                   qualityLevel=0.02, minDistance=16)
    if pts0 is None or len(pts0) < n_features:
        return None, None
    pts1, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, pts0, None)
    ok = (st.ravel() == 1)
    g0 = pts0[ok].reshape(-1, 2); g1 = pts1[ok].reshape(-1, 2)
    if len(g0) < n_features:
        return None, None
    # Keep the top-k by displacement magnitude so a dominant motion
    # shows up above noise.
    disp = np.linalg.norm(g1 - g0, axis=1)
    idx = np.argsort(-disp)[:n_features]
    return g0[idx], g1[idx]

def describe_camera_motion(dx_med, dy_med, scale_est, px_floor=1.5,
                           scale_floor=0.005):
    """Translate observed median displacement + scale into a one-line
    English description of what the CAMERA is doing. Pinned table:
    content right (dx>0)  → camera panning LEFT
    content left  (dx<0)  → camera panning RIGHT
    content down  (dy>0)  → camera tilting UP
    content up    (dy<0)  → camera tilting DOWN
    content larger (s>1)  → camera dollying IN
    content smaller(s<1)  → camera dollying OUT"""
    parts = []
    if abs(scale_est - 1) > scale_floor:
        parts.append("content expanding from center — camera is dollying IN"
                     if scale_est > 1 else
                     "content contracting toward center — camera is dollying OUT")
    if abs(dx_med) > px_floor and abs(dx_med) >= abs(dy_med):
        parts.append("content shifting RIGHT across frame — camera is panning LEFT"
                     if dx_med > 0 else
                     "content shifting LEFT across frame — camera is panning RIGHT")
    if abs(dy_med) > px_floor and abs(dy_med) > abs(dx_med):
        parts.append("content shifting DOWN in frame — camera is tilting UP"
                     if dy_med > 0 else
                     "content shifting UP in frame — camera is tilting DOWN")
    return "; ".join(parts) if parts else "no dominant motion — likely Stay"

def external_anchor(prev_bgr, curr_bgr, classify_from_M, estimate_from_pair,
                    sample_id_prev, sample_id_curr):
    """Correctness anchor on a real sampled pair. Must run before any
    per-pair classification is trusted. Returns None on pass; raises
    AssertionError on fail with a corrective action."""
    prev_g = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
    curr_g = cv2.cvtColor(curr_bgr, cv2.COLOR_BGR2GRAY)

    g0, g1 = track_features_for_anchor(prev_g, curr_g, n_features=3)
    if g0 is None:
        raise AssertionError(
            f"external anchor: too few trackable features on pair "
            f"({sample_id_prev}, {sample_id_curr}); pick a different real "
            f"pair (do NOT skip — a skipped anchor ships inverted labels)")

    dx_med = float(np.median(g1[:, 0] - g0[:, 0]))
    dy_med = float(np.median(g1[:, 1] - g0[:, 1]))

    M = estimate_from_pair(prev_g, curr_g)
    scale = float(np.hypot(M[0, 0], M[1, 0]))
    emitted = classify_from_M(M)
    prose = describe_camera_motion(dx_med, dy_med, scale)

    # Log the observed displacement + prose + emitted label so the trace
    # carries a line Gate 2 can grep (and that a self-consistent code
    # path cannot forge).
    print(f"external-anchor: pair=({sample_id_prev},{sample_id_curr}) "
          f"dx_obs={dx_med:+.2f} dy_obs={dy_med:+.2f} scale_obs={scale:.4f} "
          f"prose='{prose}' emitted={emitted}")

    # Correctness assertion: the prose and the emitted label must agree
    # on the dominant axis's direction.
    if _prose_disagrees_with_label(prose, emitted):
        raise AssertionError(
            f"external anchor FAILED: emitted {emitted} but prose says "
            f"'{prose}'. The pinned table is inverted on the disagreeing "
            f"axis for this task. Fix: flip the polarity branch in "
            f"classify_from_M on the disagreeing axis (dx>0↔Pan Left/Right "
            f"OR dy>0↔Tilt Up/Down OR scale>1↔Dolly In/Out). Do NOT "
            f"re-word the prose; do NOT skip. Re-run external_anchor "
            f"until pass, then re-run Layer B self-consistency.")
    print("external-anchor:pass")

def _prose_disagrees_with_label(prose, emitted):
    pairs = [
        ("panning LEFT",  "Pan Left"),
        ("panning RIGHT", "Pan Right"),
        ("tilting UP",    "Tilt Up"),
        ("tilting DOWN",  "Tilt Down"),
        ("dollying IN",   "Dolly In"),
        ("dollying OUT",  "Dolly Out"),
    ]
    for prose_kw, label in pairs:
        if prose_kw in prose and label not in emitted:
            # Prose asserts motion the classifier did not emit.
            return True
    return False
```

### Layer A corrective action branches

- **Pass** (`external-anchor:pass`): the pinned table matches reality
  on every observed axis of the sampled pair. Proceed to Layer B.
- **Prose/label disagreement on one axis**: flip ONLY the disagreeing
  axis's polarity in `classify_from_M` (e.g. `"Pan Left" if dx > 0`
  → `"Pan Left" if dx < 0`). Do NOT change the prose generator (that
  encodes the physics). Do NOT change `src`/`dst` ordering unless all
  three axes disagree. Re-run external_anchor on the same pair.
- **Prose/label disagreement on all three axes**: `src`/`dst` ordering
  is reversed. Fix the call to
  `estimateAffinePartial2D(src=prev_pts, dst=curr_pts)` (not the
  reverse). Re-run external_anchor.
- **Too few trackable features**: pick a different sampled pair with
  more structure (prefer a pair where the median raw-feature flow is
  larger than 2 px). Do NOT skip — a skipped anchor ships inverted
  labels silently.

### Dominant-direction red flag (post-classification)

After classifying all pairs, compute `frac_non_stay` and the per-label
fraction over all non-Stay direction labels. If any single direction
label (`Pan Right`, `Pan Left`, `Tilt Up`, `Tilt Down`, `Dolly In`,
`Dolly Out`) exceeds 60% on a scene with varied motion, OR if
`frac_non_stay > 0.90`, re-run `external_anchor` on a different sampled
pair before shipping. The combination "dominant one-direction + a
tautological self-test" is the exact signature of an inverted pinned
table.

## Layer B — Runnable 4-case self-consistency

Only after Layer A passes, run this to confirm every emitted axis has
an in-sync polarity branch given the pinned table. This is a
self-consistency check, not a correctness check — a tautological pass
here is fine as long as Layer A passed first.

```python
import cv2, numpy as np

def classify_from_M(M, th_trans=1.5, th_scale=0.005, th_rot=0.004):
    """The EXACT classifier the production path uses. Keep in sync."""
    dx, dy = float(M[0, 2]), float(M[1, 2])
    rot = float(np.arctan2(M[1, 0], M[0, 0]))
    scale = float(np.hypot(M[0, 0], M[1, 0]))
    lbl = []
    if abs(scale - 1) > th_scale:
        lbl.append("Dolly In" if scale > 1 else "Dolly Out")
    if abs(rot) > th_rot:
        lbl.append("Roll Right" if rot > 0 else "Roll Left")
    if abs(dx) > th_trans and abs(dx) >= abs(dy):
        lbl.append("Pan Left" if dx > 0 else "Pan Right")
    if abs(dy) > th_trans and abs(dy) > abs(dx):
        lbl.append("Tilt Up" if dy > 0 else "Tilt Down")
    return lbl or ["Stay"]

def estimate_from_pair(prev_gray, curr_gray):
    pts0 = cv2.goodFeaturesToTrack(prev_gray, maxCorners=400,
                                   qualityLevel=0.01, minDistance=8)
    pts1, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, pts0, None)
    g0 = pts0[st.ravel() == 1]; g1 = pts1[st.ravel() == 1]
    M, _ = cv2.estimateAffinePartial2D(g0, g1, method=cv2.RANSAC)   # src=prev, dst=curr
    return M

def _upscale_and_crop(gray, factor):
    H, W = gray.shape
    scaled = cv2.resize(gray, None, fx=factor, fy=factor,
                        interpolation=cv2.INTER_LINEAR)
    cy, cx = scaled.shape[0] // 2, scaled.shape[1] // 2
    return scaled[cy - H // 2 : cy - H // 2 + H,
                  cx - W // 2 : cx - W // 2 + W]

def sign_convention_selfconsistency(sample_frame_bgr):
    gray = cv2.cvtColor(sample_frame_bgr, cv2.COLOR_BGR2GRAY)
    SHIFT_PX = 8
    cases = [
        ("pan-left",  np.roll(gray, +SHIFT_PX, axis=1), "Pan Left"),
        ("pan-right", np.roll(gray, -SHIFT_PX, axis=1), "Pan Right"),
        ("tilt-up",   np.roll(gray, +SHIFT_PX, axis=0), "Tilt Up"),
        ("dolly-in",  _upscale_and_crop(gray, 1.05),    "Dolly In"),
    ]
    for name, curr, expected in cases:
        M = estimate_from_pair(gray, curr)
        got = classify_from_M(M)
        if expected not in got:
            raise AssertionError(
                f"self-consistency FAILED on {name}: emitted={got}, "
                f"expected={expected}. Flip the sign branch for this axis "
                f"in classify_from_M. Then re-run Layer A to confirm the "
                f"flipped branch agrees with the real-pair prose.")
        print(f"sign-test:{name}:pass")
```

## Verification + corrective action

Run order (both layers required before any per-pair classification):

1. `external_anchor(prev_bgr, curr_bgr, ...)` on
   `frames[sample_ids[0]], frames[sample_ids[1]]`. Emits
   `external-anchor:pass` (+ a prose line Gate 2 greps for English
   camera-motion vocabulary).
2. `sign_convention_selfconsistency(any_sampled_frame_bgr)`. Emits
   four tokens `sign-test:{pan-left,pan-right,tilt-up,dolly-in}:pass`.
3. Only then classify real pairs.

Branches:

- **Layer A pass, Layer B all 4 pass** → convention is pinned and
  grader-aligned on every emitted axis. Ship.
- **Layer A fail** → the pinned table is inverted for this task. Flip
  the disagreeing axis in `classify_from_M`, re-run Layer A, then
  re-run Layer B (Layer B will also pass under the flipped branch,
  tautologically — that's expected).
- **Layer A pass, Layer B fails on one axis** → an untested axis is
  out of sync with the pinned table. Flip only that axis's polarity
  branch; Layer A is already confirmed on the real-pair axis so leave
  it alone.
- **Dominant-direction red flag fires at post-classification** (one
  non-Stay label > 60%, or `frac_non_stay > 0.90`) → re-run Layer A on
  a different sampled pair; if it still passes, the dominant direction
  is real (or the threshold calibration is wrong — see
  `references/adaptive-motion-thresholds.md`).

The four `sign-test:*:pass` tokens plus the `external-anchor:pass` line
plus the prose line are what Gate 2 in `output-validation` greps for. A
pass-token line without a prose line counts as "not run" — a
tautological gate without a real-pair anchor is exactly the failure
mode this reference exists to prevent.
