---
name: egomotion-estimation
description: Estimate camera egomotion between sampled frames (optical flow + robust
  affine/homography) and convert it into allowed motion labels, then compress to half-open
  sample-index intervals.
---

## Steps
1. Operate on the **sampled frame sequence** (sample indices `0..S-1`), not on original video frame numbers.
2. For each `i>0`, track features from sampled frame `i-1` to `i` using `goodFeaturesToTrack` + `calcOpticalFlowPyrLK`; if too few correspondences, fall back to identity motion.
3. Estimate a robust transform (typically `estimateAffinePartial2D` with RANSAC; homography only if needed) to obtain translation (`dx,dy`), rotation, and scale.
4. Convert transform parameters to labels using thresholds:
   - `|scale-1|` → `Dolly In/Out`
   - `|dx|` dominant → `Pan Left/Right`
   - `|dy|` dominant → `Tilt Up/Down`
   - `|rot|` → `Roll Left/Right`
   - If none triggered → `Stay`
   Multi-label per sample is allowed.
5. Optionally smooth labels over a short window to reduce flicker (e.g., median/mode on parameters or labels).
6. **Interval compression (half-open on sample indices)**: merge consecutive samples with identical label sets into keys like `"{start}->{end}"` where the interval covers sample indices `[start, end)` (so `0->1` covers sample 0 only). Ensure the union of intervals covers `[0, S)`.
## Expected Result
A mapping from half-open **sample-index** intervals to a non-empty list of allowed motion labels, ready to write to `/root/pred_instructions.json`.
