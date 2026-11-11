# Egomotion And Dynamic-Mask Estimation

## Purpose
Produce two coupled artifacts from a monocular video: (1) per-frame multi-label camera-motion annotations compressed into half-open intervals, and (2) per-frame dynamic-object binary masks serialized in the task-declared CSR NPZ layout. Both must pass a post-write schema and path check.

## When to Use
Use when a task requires joint camera-motion classification over {Stay, Dolly, Pan, Tilt, Roll} AND dynamic-object mask output derived from residual motion after egomotion compensation. Do not fire if only one of the two deliverables is requested.

## Procedure
- Discover inputs and contract: read task statement for video path, sampled frame indices, output paths, mask shape (H, W), and exact NPZ key naming (e.g., f_{i}_data, f_{i}_indices, f_{i}_indptr). Record them; do not assume defaults.
- Egomotion per frame: goodFeaturesToTrack + calcOpticalFlowPyrLK; estimate affine/homography with RANSAC to get (tx, ty, rot, scale). On tracking failure, fall back to identity and mark the frame low-confidence.
- Calibrate thresholds from data: over a warmup window, compute robust spread (e.g., MAD) of tx/ty/rot/scale among inliers; set th_trans, th_rot, th_scale as a multiple of that spread, normalized by image dimensions. Do not hard-code literals.
- Emit multi-label set per frame using calibrated thresholds; apply windowed median smoothing; compress consecutive identical label sets into start->end half-open intervals covering all sampled frames.
- Dynamic mask per frame: warp prev to curr with the estimated transform; compute per-pixel residual (grayscale abs diff, optionally normalized by local texture); threshold using a residual-distribution rule (e.g., mean + k*std over valid region); apply morphology (open then close) and min-area filter proportional to H*W.
- Serialize masks: convert each HxW uint8 mask to scipy.sparse.csr_matrix; write arrays under the exact declared keys with dtypes uint8 (data), int32 (indices, indptr).
- Post-write validation (execution anchor): reload the NPZ and the labels artifact at their task-declared paths; assert key presence, dtypes, len(indptr)==H+1, CSR reconstruct shape==(H,W), no empty label frames, intervals cover all sampled frames. Abort and repair before finalizing if any assertion fails.

## Constraints / Pitfalls
- Never silently relocate outputs; write to the exact task-declared paths and verify existence at those paths.
- Do not embed instance-specific threshold literals; derive from the current run's residual/inlier statistics.
- Direction conventions must be consistent (image right shift implies camera pans left); document the chosen convention once and reuse.
- Multi-label allowed; forbid empty label lists (fall back to Stay).
- Mask NPZ must match the declared key schema and dtypes exactly; a shape mismatch or wrong dtype must fail the self-check loudly rather than be auto-corrected.
- If only egomotion or only masks are requested, do not emit the other artifact.