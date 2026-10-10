# Egomotion Labels And Dynamic Object Masks From Video

## Purpose
Produce two aligned per-sampled-frame deliverables from a video: (a) multi-label camera egomotion tags (Stay/Dolly/Pan/Tilt/Roll with directions) and (b) binary dynamic-object masks. Both streams must be indexed by the same sampling schedule and validated semantically, not just structurally.

## When to Use
Any task family that asks for camera motion classification together with per-frame dynamic-object segmentation from a monocular video, where the verifier checks both label semantics and mask content against hidden ground truth.

## Procedure
- Contract discovery: read the task statement and record (1) exact output paths and file formats for both labels and masks, (2) sampling fps and whether indexing is by raw frame or by sample index, (3) label vocabulary and whether multi-label is allowed, (4) mask encoding (dense vs sparse CSR, dtype, shape order). If anything is unspecified, probe provided scripts or scaffolding before guessing. Compute the expected sample count N from video duration and fps using half-open intervals aligned to sample indices.
- Egomotion estimation per sampled pair: detect features with goodFeaturesToTrack, track with calcOpticalFlowPyrLK between consecutive samples (not raw frames), fit estimateAffinePartial2D (fallback to findHomography) with RANSAC to extract (dx, dy, rotation, scale). On tracking failure, fall back to identity transform and flag the frame.
- Threshold calibration from data: collect the distribution of |dx|, |dy|, |rot|, |scale-1| across all sampled pairs; set thresholds as robust percentiles (e.g., median plus k*MAD) normalized by frame width/height and inter-sample dt. Verify the resulting Stay-rate is within a plausible band (not ~0% and not ~100%); if degenerate, widen or tighten thresholds and recompute. Emit multi-label per sample: Dolly (In/Out) from scale, Roll (Left/Right) from rotation, Pan (Left/Right) from dominant dx, Tilt (Up/Down) from dominant dy; emit Stay only when no axis exceeds its threshold. Apply temporal smoothing (windowed median) across the label stream.
- Dynamic-mask generation: warp the previous sampled frame into the current using the estimated transform; compute residual = current - warped (grayscale or multi-channel), threshold using a data-driven cutoff (e.g., percentile of residual magnitude or Otsu on robust-scaled residual), apply morphological open+close to remove speckle and connect regions, drop components below a resolution-scaled minimum area (e.g., proportional to H*W). On transform failure, fall back to raw flow-magnitude thresholding and flag the frame. Ensure exactly one mask per sampled frame (including the first, which may be all-zero or produced from the first valid pair).
- Serialize outputs to the discovered paths in the discovered formats (e.g., CSR sparse stack via scipy for masks, JSON/NPZ for labels), preserving sample-index alignment.
- Post-write reload-and-assert: reload both artifacts from disk; assert len(labels) == N and mask_array.shape[0] == N; print mask coverage ratio (fraction of pixels set) min/median/max and the label histogram; fail loudly if coverage is uniformly ~0 or ~1, or if labels are 100% Stay or 100% non-Stay without supporting motion statistics; confirm file formats match the discovered schema (dtype, sparse format, key names).

## Constraints / Pitfalls
- Do not hard-code thresholds, paths, fps, or label vocabulary; derive them from the task contract and the data distribution per run.
- Sampling must use sample-index-aligned half-open intervals at the requested fps; raw-frame indexing silently misaligns labels and masks.
- Direction conventions must be stated and consistent (image content shifting right implies camera panning left); verify on a synthetic translation before trusting outputs.
- Format-only validation is insufficient; the reload-and-assert step with coverage and label-distribution sanity checks is mandatory before claiming completion.
- Multi-label is allowed; never force a single label. Stay is emitted only when all axes are sub-threshold.
- Fallback branches (identity transform, flow-magnitude mask) must set a per-frame flag and must not silently reduce output count or change file schema.