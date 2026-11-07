# Dynamic-Object Masks With Motion Compensation

## Purpose
Produce per-sampled-frame binary masks of dynamic objects after compensating camera motion, encode them as CSR sparse arrays, and (when the task requires) emit coherent egomotion interval labels. The skill enforces model-selection, semantic plausibility, and post-write schema reload so that structurally valid outputs are also semantically defensible.

## When to Use
Apply when the task asks for dynamic/moving-object masks over sampled frames from a moving-camera video, especially when outputs must be sparse (CSR) and keyed by frame index. Do not apply for static-camera background subtraction or for optical-flow magnitude outputs; those have simpler contracts.

## Procedure
- Discover environment: probe `cv2`, `numpy`, and optionally `scipy.sparse`. If `scipy` is missing, use the numpy-only CSR path (`indices`, `indptr`, `data` arrays computed manually). Confirm input video path, frame count, sampled-index list, and required output path/keys from the task spec; do not hard-code these.
- Estimate motion per sampled pair: detect features (e.g., ORB/goodFeaturesToTrack + LK) between previous and current gray frames. First try `findHomography` with RANSAC; record inlier ratio and median residual. If inlier ratio is low or residual high relative to feature count, fall back to `estimateAffinePartial2D`. Log chosen model and metrics per frame. If both models fail (too few inliers), skip masking for that frame (emit an empty CSR) and record the reason.
- Warp and difference: warp previous gray with the chosen transform; warp an all-ones mask with `INTER_NEAREST` to obtain the `valid` region. Compute `diff = absdiff(curr_gray, warped_prev)` restricted to `valid` pixels to avoid border artifacts.
- Calibrate threshold adaptively: compute robust statistics (median and MAD) on `diff[valid]`. Choose a threshold multiplier from a small candidate set and pick the smallest multiplier whose resulting mask (after morphology + area filter) satisfies the plausibility gate below. Do not hard-code the multiplier or a minimum absolute threshold; let the data and gate decide.
- Clean up: morphological open then close with small kernels; connected-component analysis; drop components below a min-area expressed as a fraction of image area derived from the task spec or a conservative default.
- Validate semantics (execution anchor): compute `foreground_fraction = mask.sum() / mask.size` per frame. If it exceeds the configured upper cap (e.g., set from task spec, otherwise a conservative small fraction appropriate for "dynamic objects"), escalate: raise the threshold multiplier, re-run morphology, and if still above cap, switch motion model (affine->homography or vice versa) or mark the frame as parallax-dominated and emit an empty mask with a logged reason. Also sanity-check temporal consistency across neighboring sampled frames.
- Encode CSR per frame: `rows, cols = nonzero(mask)`; `indices = cols.astype(int32)`; `data = ones(nnz, uint8)`; `indptr = cumsum(bincount(rows, minlength=H), prepend=0).astype(int32)`. Store under the required key pattern derived from the task spec (commonly `f_{i}_data/indices/indptr`) and store `shape=[H,W]` as `int32`.
- Post-write schema check (execution anchor): reload each written frame's arrays and assert `len(indptr)==H+1`, `indptr[-1]==indices.size`, `indices.dtype==int32`, `data.dtype==uint8`, and `shape==[H,W]`. Only after all sampled frames pass declare completion.
- If the task also requires egomotion interval labels: derive labels from the decomposed per-interval transform (translation and rotation components). Fix sign conventions explicitly from the task's allowed label vocabulary (e.g., which sign of horizontal translation maps to Pan Left vs Pan Right, which sign of vertical translation maps to Tilt Up vs Tilt Down, which of scale vs forward translation maps to Dolly In vs Dolly Out) by inspecting the task spec or a one-shot example; do not improvise. Merge consecutive intervals with identical label sets.

## Constraints / Pitfalls
- Do not treat border fill as foreground; always restrict statistics and thresholding to the warped valid region.
- Do not hard-code threshold literals (no fixed `20`, no fixed `3*MAD`, no fixed min-area). Derive them from data and the plausibility gate.
- Structural self-checks are not sufficient. A schema-valid CSR with 15 percent foreground on a "dynamic objects" task is almost always wrong; the plausibility gate must gate completion.
- Affine motion alone cannot model 3D parallax; always attempt homography first and record the inlier ratio before falling back.
- Keep fallback branches bounded: at most one model switch and one threshold-tightening pass per frame, then emit an empty mask with a logged reason rather than looping.
- Do not invent output keys, frame indices, or label vocabularies; read them from the task spec or discovered schema.
- Keep all source and comments in printable ASCII.