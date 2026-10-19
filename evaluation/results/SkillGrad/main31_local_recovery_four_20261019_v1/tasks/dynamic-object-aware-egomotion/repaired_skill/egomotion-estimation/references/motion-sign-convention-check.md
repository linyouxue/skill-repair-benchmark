# Motion sign-convention check (warp + residual + label mapping)

Use this when you have a directionful camera-motion label set (Pan Left/Right, Tilt Up/Down, Roll Left/Right) derived from an estimated transform or optical flow and you need to ensure you did not invert semantics.

## Goal
Empirically validate:
1) which direction your estimated transform maps (`prev→curr` vs `curr→prev`), and
2) how image-motion direction maps to camera-motion labels for your pipeline.

## Minimal runnable routine (with runtime branches)

```python
import numpy as np
import cv2

def to_gray(img_bgr):
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

def warp_with_2x3(gray, M_2x3):
    H, W = gray.shape[:2]
    return cv2.warpAffine(gray, M_2x3, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)

def robust_affine(prev_gray, curr_gray, max_corners=800):
    p0 = cv2.goodFeaturesToTrack(prev_gray, max_corners, 0.01, 10)
    if p0 is None or len(p0) < 20:
        return None, None, "too_few_features"
    p1, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, p0, None)
    good0 = p0[st.reshape(-1) == 1]
    good1 = p1[st.reshape(-1) == 1]
    if len(good0) < 20:
        return None, None, "too_few_tracks"
    M, inl = cv2.estimateAffinePartial2D(good0, good1, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if M is None:
        return None, None, "ransac_failed"
    return M, inl, "ok"

def residual_l1(a, b, valid=None):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    if valid is None:
        return float(np.mean(d))
    v = d[valid]
    return float(np.mean(v)) if v.size else float("inf")

# Inputs: load two consecutive frames from your sampled set
# prev_bgr, curr_bgr = ...
prev_gray = to_gray(prev_bgr)
curr_gray = to_gray(curr_bgr)

M, inl, status = robust_affine(prev_gray, curr_gray)
if status != "ok":
    # Branch A: transform estimation unreliable → do not emit directionful labels
    labels = ["Stay"]
    print("Affine estimation failed:", status, "→ fallback labels:", labels)
else:
    # Branch B: test both warp directions and pick the one that reduces residual
    warped_prev = warp_with_2x3(prev_gray, M)
    M_inv = cv2.invertAffineTransform(M)
    warped_curr = warp_with_2x3(curr_gray, M_inv)

    # valid masks to ignore border fill
    H, W = prev_gray.shape[:2]
    ones = np.ones((H, W), np.uint8)
    valid_prev_to_curr = warp_with_2x3(ones, M) > 0
    valid_curr_to_prev = warp_with_2x3(ones, M_inv) > 0

    r_prev_to_curr = residual_l1(curr_gray, warped_prev, valid_prev_to_curr)
    r_curr_to_prev = residual_l1(prev_gray, warped_curr, valid_curr_to_prev)

    direction = "prev_to_curr" if r_prev_to_curr <= r_curr_to_prev else "curr_to_prev"
    print("residual(prev→curr):", r_prev_to_curr, "residual(curr→prev):", r_curr_to_prev)
    print("chosen_direction:", direction)

    dx = float(M[0, 2]); dy = float(M[1, 2])
    # IMPORTANT: dx,dy are in the coordinate mapping you estimated (prev→curr for estimateAffinePartial2D above).
    # If you instead choose curr→prev as your operational direction, negate by using M_inv.
    if direction == "curr_to_prev":
        dx = float(M_inv[0, 2]); dy = float(M_inv[1, 2])

    # Example mapping: image shifts right (dx>0) typically corresponds to camera panning left,
    # but treat this as a hypothesis until you confirm visually on a few clips.
    pan_label = "Pan Left" if dx > 0 else "Pan Right"
    tilt_label = "Tilt Up" if dy > 0 else "Tilt Down"
    labels = [pan_label, tilt_label]
    print("dx,dy used:", dx, dy, "→ provisional:", labels)
```

## Verification + corrective action

Verification checklist on 3–5 randomly sampled transitions:
- Residual after the chosen warp direction should be **lower** than the unwarped residual.
- The chosen direction should be **consistent** across pairs (not flipping randomly).
- The provisional label should match what you observe by quickly saving a side-by-side diagnostic:
  - draw an arrow of the median LK flow vector on the image, or
  - write one debug PNG with `curr` and `warp(prev)` difference heatmap.

Corrective action if verification fails:
- If the residual does not improve: increase feature count / LK window, switch to homography, or treat the clip as unreliable and emit conservative labels (e.g., Stay) for those frames.
- If residual improves but labels look inverted: keep the chosen warp direction, but **flip the mapping rule** (Pan Left ↔ Pan Right and/or Tilt Up ↔ Tilt Down), then re-run the same 3–5 transition check.
- If direction choice flips across time: apply temporal smoothing to transform parameters or compute motion from a longer baseline (e.g., compare against a sliding reference frame).
