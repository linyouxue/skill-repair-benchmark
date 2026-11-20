---
name: egomotion-estimation
description: "Estimate camera motion with optical flow + affine/homography, allow multi-label per frame."
---

# When to use
- You need to classify camera motion (Stay/Dolly/Pan/Tilt/Roll) from video, allowing multiple labels on the same frame.

# Workflow
1) **Feature tracking**: `goodFeaturesToTrack` + `calcOpticalFlowPyrLK`; drop if too few points. Pre-convert to grayscale.
2) **Robust transform**: `estimateAffinePartial2D` (or homography) with RANSAC to get `dx, dy, rotation, scale` between consecutive *sampled* frames.
3) **Thresholding** on the *per-sampled-frame* motion (not per native frame):
   - `th_trans` in pixels per sampled step, `th_rot` in radians, `th_scale` as a relative delta.
   - Because sampling multiplies the inter-sample motion by `step = src_fps / target_fps`, raise `th_trans` proportionally; do not reuse per-native-frame thresholds blindly.
   - Allow **truly independent** labels on the three axes (scale, rotation, translation). Each axis should be decided on its own `if` — do not gate one axis on another's magnitude.
4) **Temporal smoothing** (optional): windowed mode/median of each axis's label to reduce flicker before interval compression.
5) **Interval compression**: scan sampled frames and merge consecutive frames with identical label *sets* into a single `"start->end"` key with half-open `end`.

# Decision sketch (multi-label)
```python
labels = []
for i in range(1, n_samples):                 # frame 0 has no prior; handle below
    lbl = []
    if abs(scale - 1) > th_scale:
        lbl.append("Dolly In" if scale > 1 else "Dolly Out")
    if abs(rot) > th_rot:
        lbl.append("Roll Right" if rot > 0 else "Roll Left")
    # Pan and Tilt are INDEPENDENT axes — emit both when both exceed threshold.
    if abs(dx) > th_trans:
        # image shifts right (dx>0) when the camera pans left, and vice versa
        lbl.append("Pan Left" if dx > 0 else "Pan Right")
    if abs(dy) > th_trans:
        # image shifts down (dy>0) when the camera tilts up, and vice versa
        lbl.append("Tilt Up" if dy > 0 else "Tilt Down")
    if not lbl:
        lbl.append("Stay")
    labels.append(lbl)
```

# Coverage for sampled frame 0
- Frame 0 has no previous frame, so it has no measured transform. Give it a label (commonly `["Stay"]`, or copy the label set of frame 1) so that the interval compression covers the full half-open range `[0, n_samples)` with no gap at the front.

# Heuristic starting points
- Scale thresholds with the sampling stride; a translation threshold that works at native fps is typically too small after sub-sampling.
- Prefer rotation in **degrees** mentally (`th_rot = deg2rad(≈1°)`) and scale as a **relative** delta (`~0.01` for 1%).
- Low texture / low light: increase feature count, use larger LK windows (e.g. `winSize=(21,21), maxLevel=3`), and relax RANSAC settings.
- Decompose affine robustly: `dx = M[0,2]`, `dy = M[1,2]`, `scale = sqrt(M[0,0]**2 + M[0,1]**2)`, `rot = atan2(M[0,1], M[0,0])`.

# Self-check
- [ ] Fallback to identity transform on tracking/RANSAC failure; never emit empty labels.
- [ ] Direction conventions consistent (image right shift = camera pans left; image down shift = camera tilts up).
- [ ] Pan and Tilt are decided by independent `if abs(dx)>th_trans` / `if abs(dy)>th_trans` (not mutually exclusive).
- [ ] Multi-label allowed on all three axes simultaneously (e.g. `Dolly In + Pan Right + Tilt Up`).
- [ ] Translation threshold scaled for the sampling stride, not just a per-native-frame value.
- [ ] Sampled frame 0 is covered by the first interval.
- [ ] Compressed intervals partition the half-open range `[0, n_samples)`; keys formatted as `"start->end"` with integers only.
