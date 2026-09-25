# SKILL.md

## When to use
Use this skill when a task asks you to (1) analyze **camera egomotion** over time in a given video and (2) output **per-sampled-frame dynamic-object binary masks**, writing results to two required files with strict formats:
- A **JSON** mapping **half-open frame intervals** (`"start->end"`) to a **list of motion labels** chosen from a fixed vocabulary.
- An **NPZ** containing the **mask resolution** and, for each sampled frame, a **CSR sparse encoding** of `True` pixels.

Before acting, gather evidence from the target context and the video:
- Confirm the required **sampling rate** (fps) and compute sampled frame indices/timestamps.
- Inspect video properties (frame count, native fps, resolution) and ensure your sampling plan is consistent.
- Decide how you will infer camera motion robustly in the presence of moving objects (e.g., global motion estimation with outlier rejection).
- Decide how you will detect dynamic objects (e.g., motion inconsistency vs. estimated background motion).

## Possible Failure Modes
- **Sampling mismatch**: sampling at the video’s native fps (or wrong step) instead of the required sampling rate; off-by-one in sampled indices.
- **Interval semantics wrong**: treating `"a->b"` as closed range instead of **half-open**; leaving gaps or overlaps between intervals; not covering all sampled frames.
- **Invalid motion labels**: outputting labels not in the allowed set, wrong capitalization, or outputting a string instead of a list of strings.
- **Over-fragmented intervals**: producing a separate interval for every frame due to noisy motion estimates instead of merging stable segments.
- **Confusing camera vs. object motion**: labeling camera motion based on dominant moving objects rather than background; failing to use robust estimation (e.g., RANSAC) to ignore outliers.
- **Mask format errors in NPZ**:
  - Missing `shape` key or wrong order (must be `[H, W]`).
  - Saving dense masks instead of CSR components, or using wrong key names (must follow `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr`).
  - CSR arrays inconsistent (bad `indptr` length, indices out of bounds, data not aligned with indices).
  - Mask resolution not matching sampled frame resolution.
- **Wrong mask meaning**: marking static background as dynamic due to camera motion; not compensating for estimated camera motion when segmenting dynamics.
- **Clobbering/relocating outputs**: writing files to the wrong paths/names; not producing exactly the required filenames.

## Possible procedures
1. **Load video and define sampling**
   - Read video metadata (native fps, frame count, H×W).
   - Compute sampled frame indices for the required sampling rate (e.g., using timestamps or integer stepping derived from native fps).
   - Decode only sampled frames to reduce compute; keep a consistent sampled-frame index `i = 0..N-1`.

2. **Estimate global camera motion between sampled frames**
   - For each pair of consecutive sampled frames:
     - Compute correspondences (optical flow, feature matching).
     - Fit a **global motion model** (e.g., affine/homography) with **outlier rejection** (RANSAC) to reduce influence from dynamic objects.
   - Derive motion descriptors from the fitted model and/or average flow:
     - Horizontal translation/rotation tendency → pan left/right.
     - Vertical translation/rotation tendency → tilt up/down.
     - Scale change → dolly in/out.
     - In-plane rotation → roll left/right.
     - Near-zero transform → stay.
   - Add smoothing:
     - Temporal filtering (median/majority vote over a short window) to reduce jitter.
     - Thresholds with hysteresis to avoid frequent label flips.

3. **Convert per-step motion into interval JSON**
   - Produce a motion label set for each **step** (between sampled frames) or each sampled frame, depending on how you interpret “intervals”; then convert to the required `"start->end"` half-open ranges.
   - Merge consecutive indices with identical label lists into longer intervals.
   - Ensure intervals are contiguous, non-overlapping, and cover the sampled index domain required by the evaluator.

4. **Detect dynamic objects per sampled frame**
   - Use the estimated camera motion to compensate for egomotion:
     - Warp the previous frame into the current frame using the global transform and compute residuals; or
     - Compute flow and subtract the global (background) motion component; pixels with large residuals are candidates for dynamic objects.
   - Post-process to obtain a clean binary mask:
     - Threshold residual magnitude and optionally enforce consistency across time.
     - Morphological opening/closing to remove speckle and fill small holes.
     - Optional connected-component filtering by size to remove noise.
   - Confirm mask is boolean with shape `[H, W]` matching the sampled frame.

5. **Encode masks as CSR into NPZ**
   - For each sampled frame index `i`:
     - Convert the boolean mask to a CSR representation (row-wise):
       - `indptr`: length `H+1`, cumulative counts per row.
       - `indices`: column indices of `True` pixels (sorted within each row is typical).
       - `data`: values for each stored entry (can be `1`/`True`; keep consistent dtype).
   - Save an `.npz` with:
     - `shape = [H, W]`
     - For each `i`: `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr`

6. **Recovery / debugging steps**
   - If motion labels are unstable: increase smoothing window, tighten thresholds, or prefer model-based (homography/affine) cues over raw flow averages.
   - If dynamic masks are too dense due to camera motion: improve egomotion compensation (better RANSAC, better features), or raise residual thresholds.
   - If masks miss movers: lower thresholds or incorporate temporal accumulation (object persists across a few frames).

## Verification Checklist
- **Sampling**
  - [ ] Sampled frames correspond to the required sampling rate and produce a consistent sampled index sequence `0..N-1`.
- **JSON output**
  - [ ] File exists at the required path/name and is valid JSON.
  - [ ] Keys are in `"start->end"` form with integers; interpreted as **half-open** intervals.
  - [ ] Interval coverage has no gaps/overlaps across the sampled index domain.
  - [ ] Each value is a **list** of labels; every label is in the allowed label set and correctly spelled/cased.
- **NPZ output**
  - [ ] File exists at the required path/name and is loadable as NPZ.
  - [ ] Contains `shape` exactly as `[H, W]` matching sampled frame resolution.
  - [ ] For every sampled frame `i`, keys `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr` exist.
  - [ ] CSR validity checks: `len(indptr)==H+1`, `indptr[0]==0`, `indptr[-1]==len(indices)==len(data)`, and all `indices` are within `[0, W-1]`.
  - [ ] Reconstructing a dense mask from CSR yields a boolean array of shape `(H, W)` with `True` at intended locations.
- **Evaluator-visible constraints**
  - [ ] Output filenames and locations exactly match the required ones.
  - [ ] No reliance on retrieved examples’ concrete constants/paths/IDs; only the target context dictates requirements.
  - [ ] Unrelated files/state are not modified; only the required outputs are created/overwritten.
- **Sanity check**
  - [ ] Quick visualization/spot-check on a few sampled frames: camera motion labels look plausible; dynamic masks highlight moving objects rather than the whole frame.
