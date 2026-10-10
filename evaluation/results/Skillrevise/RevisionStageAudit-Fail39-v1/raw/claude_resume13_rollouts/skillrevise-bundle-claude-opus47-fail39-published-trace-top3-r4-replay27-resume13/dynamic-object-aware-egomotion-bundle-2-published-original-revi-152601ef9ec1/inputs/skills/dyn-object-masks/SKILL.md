# dyn-motion-and-masks

## Purpose
Produce two aligned artifacts for sampled video frames: (a) per-frame dynamic-object binary masks in CSR sparse form after global motion compensation, and (b) per-interval egomotion labels using documented sign conventions. Validate both before declaring completion.

## When to Use
Tasks that require sparse dynamic masks and/or discrete camera-motion labels (Pan, Tilt, Roll, Dolly, Stay) for frames sampled from a monocular video with moving camera.

## Procedure
- Discover contract: read task spec for required output paths, sampling rule (derive from fps if given), label vocabulary, axis conventions, and CSR key format. Do not invent labels or keys not in the spec.
- Sample frames per the declared rule; for each consecutive sampled pair compute grayscale and estimate a global transform: start with affine (estimateAffinePartial2D with RANSAC). If median residual on the valid region exceeds the per-video noise floor (median diff of a near-static pair, or a self-measured MAD baseline), re-estimate with homography (findHomography, RANSAC) and reuse.
- Warp previous frame and an all-ones mask with the chosen transform; compute diff only on valid pixels. Set threshold as median(valid_diff) + k * 1.4826 * MAD(valid_diff) with k chosen from the task spec or defaulted to a small integer; do not hard-code an absolute floor. Open-then-close with kernels sized as a function of min(H,W); drop components below a min-area expressed as a fraction of image area.
- Label egomotion from the chosen transform using conventions documented below; prefer Stay when per-axis magnitudes fall below a self-computed noise floor from near-static pairs. Allow multi-label only when the spec permits.
- Encode CSR without scipy: rows, cols = np.nonzero(mask); indices = cols.astype(int32); data = np.ones(nnz, uint8); indptr = np.concatenate(([0], np.cumsum(np.bincount(rows, minlength=H)))). Store shape = [H, W] int32.
- Validate: reload each f_{i}_data/indices/indptr, reconstruct dense mask, assert len(indptr)==H+1, indptr[-1]==indices.size, indices sorted within each row, dtypes correct; print per-frame coverage and the label histogram. Fail loudly if coverage is ~0 or ~1 across all frames, or if every frame received an identical multi-label set.

## Constraints / Pitfalls
- Axis conventions (OpenCV image coords, y-down): Pan Left/Right from sign of horizontal translation of static background in the warp; Tilt Up/Down from vertical translation; Roll from rotation angle sign under y-down (clockwise in image = negative math angle); Dolly In/Out from average scale > 1 or < 1 (or median flow divergence). Verify sign on one known pair before committing.
- No scipy dependency; use numpy-only CSR. Do not shell-install packages in externally-managed environments.
- No hard-coded literal thresholds, kernel sizes, or min-areas; derive from image size and valid-region statistics. Do not inflate thresholds using the signal they gate.
- Keys, intervals (half-open vs closed), label vocabulary, and file layout must come from the task spec, not from this skill.
- Never claim completion before the reload-and-assert validation step passes and the coverage and label-histogram sanity checks print non-degenerate distributions.