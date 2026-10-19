# Motion sign-convention check (transform direction + camera-vs-image motion)

Use this when you estimated global motion (affine/homography or dominant optical flow) and must map it into **directionful** semantic labels (Pan Left/Right, Tilt Up/Down, Roll Left/Right). This procedure prevents a common failure mode: outputs that are structurally valid but consistently flipped in direction.

## 1) Establish what your transform means
Decide and write down one sentence:
- **Option A (common):** `M_prev_to_curr` maps points in the **previous** frame to the **current** frame.
- **Option B:** `M_curr_to_prev` maps points in the **current** frame to the **previous** frame.

If you used `estimateAffinePartial2D(src_pts, dst_pts)`, then the returned matrix maps `src_pts → dst_pts` (so name it accordingly).

## 2) Branch: confirm warp direction reduces residual
Runtime branch: apply the transform in the hypothesized direction and check whether it actually aligns images.

```python
import cv2
import numpy as np

def warp_residual(prev_gray: np.ndarray, curr_gray: np.ndarray, M_2x3: np.ndarray) -> float:
    H, W = prev_gray.shape[:2]
    warped = cv2.warpAffine(prev_gray, M_2x3, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    valid = cv2.warpAffine(np.ones((H, W), np.uint8), M_2x3, (W, H), flags=cv2.INTER_NEAREST) > 0
    diff = cv2.absdiff(curr_gray, warped)
    return float(np.mean(diff[valid]))

# Inputs: prev_gray, curr_gray from a real sampled pair; M from your estimator
res = warp_residual(prev_gray, curr_gray, M)
res_id = warp_residual(prev_gray, curr_gray, np.array([[1,0,0],[0,1,0]], dtype=np.float32))

if res >= res_id:
    print("Warp did not improve residual; transform direction may be inverted or M is poor.")
else:
    print("Warp improves residual; direction is plausibly correct.")
```

**If `res >= res_id`:**
- Try inverting the transform (for affine: invert the 3×3 lift) and re-check residual.
- If both are bad, your motion estimate is unreliable on this pair; increase features / adjust RANSAC, or skip this pair and test another.

## 3) Branch: compute dominant image motion and compare to provisional labels
Use either affine parameters or median LK flow. Compare the sign to what you *think* “Pan Left/Right” etc. should mean.

```python
import numpy as np

def affine_params(M_2x3: np.ndarray):
    dx = float(M_2x3[0, 2]); dy = float(M_2x3[1, 2])
    rot = float(np.arctan2(M_2x3[1, 0], M_2x3[0, 0]))
    return dx, dy, rot

# Optional: you may also have flow vectors of shape (N,2)

def median_flow(flow_xy: np.ndarray):
    med = np.median(flow_xy, axis=0)
    return float(med[0]), float(med[1])

# Branch A: affine-based
if M is not None:
    dx, dy, rot = affine_params(M)
    print({"dx": dx, "dy": dy, "rot_rad": rot})

# Branch B: flow-based
if flow_xy is not None and len(flow_xy) > 0:
    fx, fy = median_flow(flow_xy)
    print({"flow_median_x": fx, "flow_median_y": fy})
```

Interpretation reminder (must be validated visually on your data):
- **Image motion** is what flow/warp shows (where pixels/features moved).
- **Camera motion** is often the opposite direction for pure pan/tilt (e.g., content shifts right when the camera pans left), but this depends on whether you are labeling camera motion or apparent image motion.

If your task expects **camera motion labels**, then a good default hypothesis is:
- image shifts right ⇒ camera pans left
- image shifts down ⇒ camera tilts up
…but you must verify on at least 2–3 transitions.

## 4) Verification (semantic) + corrective action
Verification step:
1) Pick 2–3 transitions (not all identical frames).
2) For each, print `(dx, dy, rot)` (or median flow) and the provisional label.
3) Manually inspect quickly by saving a debug overlay (optional) or by checking that the label agrees with the sign across those samples.

If there is a consistent mismatch (e.g., all samples indicate `dx>0` but your labels should be the opposite):
- Flip the mapping rule for that axis (Pan, Tilt, or Roll) **and rerun this chapter**.
- After flipping, re-run the warp residual check to ensure you did not accidentally switch transform direction instead of label mapping.

If mismatch is inconsistent across samples:
- Your global motion estimate may be contaminated by dynamic objects; increase outlier rejection, mask moving regions (if available), or reduce reliance on translation-only heuristics.
