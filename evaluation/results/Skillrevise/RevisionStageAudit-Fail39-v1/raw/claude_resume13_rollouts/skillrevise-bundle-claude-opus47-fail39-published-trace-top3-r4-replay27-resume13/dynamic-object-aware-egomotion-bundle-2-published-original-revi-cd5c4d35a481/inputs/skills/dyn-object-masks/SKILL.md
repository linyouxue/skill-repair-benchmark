# dyn-motion-and-masks

## Purpose
Produce two aligned artifacts for sampled video frames: per-frame dynamic-object binary masks in CSR sparse form after global motion compensation, and per-interval egomotion labels. All sign conventions and thresholds are self-calibrated from measured signals, never asserted from prose.

## When to Use
Monocular video tasks requiring numpy-only CSR dynamic masks and discrete camera-motion labels from a task-declared vocabulary (e.g., Pan, Tilt, Roll, Dolly, Stay) across sampled frames.

## Procedure
- Discover contract: read spec for output paths, sampling rule, label vocabulary, pair-to-frame alignment (e.g., does pair (i, i+1) label frame i or i+1), interval semantics, CSR keys, and whether multi-label is permitted. Record unknowns; do not invent.
- Calibrate signs: pick one real frame F. Build synthetic pairs by applying known transforms to F: (+dx, +dy), (-dx, -dy), (+rot), (-rot), (scale>1), (scale<1). Run the same estimator used downstream. Record a dict mapping estimator parameter sign/magnitude to each label axis. If any mapping is ambiguous or inverted vs spec examples, stop and recompute.
- Measure noise floor: run estimator on a synthetic identity pair (F vs F with sub-pixel jitter) and on the real pair with smallest raw inter-frame diff. Set per-axis Stay thresholds to the max of these two MADs. Forbid absolute image-fraction literals for Stay thresholds.
- Compute masks per real pair: estimate affine (RANSAC); if median residual on valid region exceeds the noise floor by a spec-declared or self-measured factor, re-estimate with homography. Warp previous frame and an all-ones mask; threshold valid diff at median + k * 1.4826 * MAD with k from spec. Open-then-close with kernels sized from min(H,W); drop components below a min-area derived from measured background-noise component sizes, not an image-fraction literal.
- Label egomotion using the calibrated sign dict and noise-floor thresholds. Default to Stay per axis when below the floor. Cross-check Dolly against median flow divergence; discard Dolly if divergence disagrees in sign.
- Handle first/last sampled frame per spec; if unspecified, align pair (i, i+1) to frame i and set the final frame's mask/label from the previous pair.
- Encode CSR without scipy: indices=int32 cols, data=uint8 ones, indptr from cumulative row counts, shape=[H,W] int32.
- Validate: reload each f_{i}_data/indices/indptr; assert len(indptr)==H+1, indptr[-1]==indices.size, indices sorted per row, dtypes correct. Print per-frame coverage and label histogram.
- Degeneracy gate: fail and recalibrate if any single label tuple covers >70% of pairs, any single axis fires in >90% of pairs without flow-divergence agreement, or coverage is ~0 or ~1 across all frames.

## Constraints / Pitfalls
- Never commit sign conventions from prose; only from the synthetic calibration dict produced this run.
- No hard-coded literal thresholds, kernel sizes, min-areas, or k values; derive from noise floor and spec.
- Keys, vocabulary, pair-to-frame alignment, and multi-label policy come from the spec, not this skill.
- No scipy; no shell-installing packages in externally-managed environments.
- Do not declare completion before calibration dict, noise floor print, CSR reload-and-assert, and degeneracy gate all pass.