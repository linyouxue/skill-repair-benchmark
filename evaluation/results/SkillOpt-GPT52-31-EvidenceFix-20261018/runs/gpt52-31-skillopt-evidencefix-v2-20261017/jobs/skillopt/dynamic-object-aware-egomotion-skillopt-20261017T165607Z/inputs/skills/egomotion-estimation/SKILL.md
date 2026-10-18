---
name: egomotion-estimation
description: "Estimate camera motion with optical flow + affine/homography, allow multi-label per frame."
---

# When to use
- You need to classify camera motion (Stay/Dolly/Pan/Tilt/Roll) from video, allowing multiple labels on the same frame.
- You also need **stable global frame-to-frame transforms for warping/alignment** (e.g., background compensation before dynamic-object masking). The estimated transform must be usable both for motion labeling **and** for robust frame warps.

# Workflow
1) **Feature tracking (alignment-oriented)**: `goodFeaturesToTrack` + `calcOpticalFlowPyrLK`.
   - Enforce **well-distributed sampling**: detect in a grid / use `goodFeaturesToTrack` with a mask per cell so points cover the whole image (not only one textured region).
   - Track quality gates: forward-backward check, drop points with high LK error, and drop if too few **and/or too clustered** points.
2) **Robust transform (for warping)**:
   - Prefer estimating a transform you will actually use to warp frame i-1 → i.
   - Use `estimateAffinePartial2D` for mostly planar/weak perspective scenes; switch to **homography** (`findHomography`/`estimateAffine2D` vs partial) when there is strong rotation, wide FOV, or visible perspective/parallax (e.g., camera yaw with depth variation).
   - Use RANSAC/LMEDS and inspect inliers: require a minimum inlier count and inlier ratio; reject degenerate solutions (e.g., near-singular matrices, extreme scale).
   - Practical robustness: run a two-stage fit (coarse RANSAC → re-fit on inliers) to reduce jitter.
3) **Warp application** (for downstream dynamic-object masking):
   - Use the estimated transform to warp the previous frame into the current frame; alignment quality directly affects compensated differencing.
   - If the transform fails quality checks, **fallback to identity** (or last good transform) to avoid injecting large false motion.
4) **Temporal smoothing (transform-first)**:
   - Smooth transforms (or their parameters) over time to reduce flicker in warps; prefer smoothing in a consistent parameterization (e.g., dx/dy/rot/scale, or cumulative SE(2) then differentiate) rather than smoothing labels only.
5) **Thresholding (labels derived from the stabilized transform)**  
   - Translate threshold `th_trans` (px/frame), rotation (rad), scale delta (ratio).  
   - Allow multiple labels: if scale and translate are both significant, emit Dolly + Pan; rotation independent for Roll.
6) **Interval compression**: merge consecutive frames with identical label sets into `start->end`.

# Decision sketch
```python
labels=[]
for each frame i>0:
    lbl=[]
    if abs(scale-1)>th_scale: lbl.append("Dolly In" if scale>1 else "Dolly Out")
    if abs(rot)>th_rot: lbl.append("Roll Right" if rot>0 else "Roll Left")
    if abs(dx)>th_trans and abs(dx)>=abs(dy): lbl.append("Pan Left" if dx>0 else "Pan Right")
    if abs(dy)>th_trans and abs(dy)>abs(dx): lbl.append("Tilt Up" if dy>0 else "Tilt Down")
    if not lbl: lbl.append("Stay")
    labels.append(lbl)
```

# Heuristic starting points (720p, high fps; scale with resolution/fps)
- Tune thresholds based on resolution and frame rate (e.g., normalize translation by image width/height, rotation in degrees, scale as relative ratio).
- Low texture/low light: increase feature count, use larger LK windows, and relax RANSAC settings.



## Transform quality tips (to improve global alignment + reduce mask flicker)
- **Feature distribution**: aim for tracks across foreground/background and across the full image; if most points are in one corner, warps will be unstable and compensated differencing will hallucinate motion elsewhere.
- **Outlier rejection**: use forward-backward flow filtering and RANSAC inlier masks; reject estimates with low inlier ratio or inliers concentrated along a line (degenerate for homography/affine).
- **Homography vs affine**: choose homography when perspective effects dominate (strong yaw/roll, wide FOV) but be cautious in heavy parallax scenes; if homography becomes unstable, consider affine fallback plus stronger smoothing.
- **Smoothing strategy**: smooth transform parameters (dx/dy/rot/scale) or smooth cumulative transforms, then re-differentiate per-frame motion; this typically lowers temporal flicker in dynamic-object masks more than label-only smoothing.
# Self-check
- [ ] Fallback to identity transform on failure; never emit empty labels.
- [ ] Direction conventions consistent (image right shift = camera pans left).
- [ ] Multi-label allowed; no forced single label.
- [ ] Compressed intervals cover all sampled frames; keys formatted correctly. 

- [ ] Transform is numerically sane (no near-singular matrix / extreme scale) and has sufficient, well-distributed inliers.
- [ ] Warping `prev -> curr` reduces background difference (quick sanity check on a few frames) and does not introduce obvious jitter.
- [ ] Transform smoothing is applied before differencing so dynamic-object masks do not flicker due to per-frame estimation noise.
