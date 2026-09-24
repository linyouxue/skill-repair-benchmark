---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the task requires analyzing a video to produce two paired artifacts describing per-frame camera egomotion and dynamic-object segmentation, sampled at a fixed fps. The binding contract requires:
- Reading a video from a given path and sampling frames at the specified fps.
- Producing a JSON that maps half-open frame intervals (`"start->end"`) to a list of motion labels from a fixed allowed vocabulary (stay / dolly / pan / tilt / roll variants).
- Producing an `.npz` archive containing a `shape` array `[H, W]` plus, for every sampled frame `i`, three CSR sparse arrays keyed as `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr` that encode a binary dynamic-object mask.

Before acting, gather: video dimensions and total frame count, actual sampling indices given the fps, the exact label vocabulary the evaluator expects, the CSR sparse layout convention (per-row indptr of length H+1), and whether any pretrained motion/segmentation models are available in the environment. Retrieved BigCodeBench examples only illustrate generic JSON I/O patterns; they do not constrain schema here.

## Possible Failure Modes
- Using the wrong sampling rate or mis-mapping sampled indices back to original frame indices; the interval keys must index sampled frames (0, 1, 2, ...), not raw video frames.
- Emitting interval keys as closed ranges or off-by-one (e.g., `"0->0"` for a single frame) instead of the required half-open `"i->i+1"`.
- Writing motion labels with wrong casing, punctuation, or synonyms (e.g., "pan_left", "PanLeft", "Zoom In") instead of the exact allowed strings.
- Storing labels as a string instead of a list; the value for each interval must be a list even when there is only one label.
- Omitting the `shape` key in the `.npz`, or storing it as a tuple/scalar instead of a length-2 array `[H, W]`.
- Building CSR incorrectly: e.g., using COO or flat boolean arrays, forgetting that `indptr` must have length `H+1`, or swapping rows/columns so `indices` indexes rows instead of columns.
- Missing frames in the `.npz` (must have entries for every sampled frame index used in the JSON) or an index mismatch between the JSON intervals and the mask frames.
- Producing masks at a different resolution than the value written under `shape`.
- Silently skipping frames when the video has fewer frames than expected, causing key gaps.
- Overwriting or corrupting unrelated files at `/root/`; write only the two required paths.

## Possible procedures
1. Load the video (e.g., with OpenCV/decord/ffmpeg), read fps and frame count, and compute sampled frame timestamps at `fps=5`. Deduplicate and index them as `0..N-1`.
2. For egomotion: obtain per-sampled-frame motion using either a pretrained egomotion/optical-flow model or a classical pipeline (feature matching + essential matrix / homography decomposition). Convert the dominant motion component per frame into exactly one (or more) of the allowed labels. Default to `Stay` when motion magnitude is below a threshold.
3. Emit intervals: the simplest safe form is one entry per sampled frame as `"i->i+1": [label]`. Optionally merge consecutive identical labels into longer intervals, but keep the half-open semantics.
4. For dynamic-object masks: run a segmentation/motion-segmentation approach (e.g., moving-object detector, ego-motion-compensated flow residual, or an off-the-shelf video object segmentation model). Produce a boolean `H×W` mask per sampled frame at a consistent resolution.
5. Convert each dense boolean mask to `scipy.sparse.csr_matrix` and store `.data`, `.indices`, `.indptr` under keys `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr`. Add `shape=np.array([H, W])`. Save with `np.savez` (or `savez_compressed`).
6. Cross-check: the set of frame indices `i` used in the JSON intervals must match the set of `f_{i}_*` groups in the `.npz`.

Decision points:
- If no dynamic objects are detected in a frame, still write an all-False CSR mask (valid empty `data`/`indices`, `indptr` of zeros length `H+1`) rather than omitting the frame.
- If motion estimation fails on a frame (e.g., too few features), fall back to `Stay` rather than skipping.
- If model dependencies are unavailable, prefer a lightweight classical pipeline over failing.

## Verification Checklist
- [ ] `/root/pred_instructions.json` exists, is valid JSON, and every key matches the pattern `"<int>-><int>"` with `end == start + k` for `k >= 1` and half-open semantics.
- [ ] Every label is exactly one of: `Stay, Dolly In, Dolly Out, Pan Left, Pan Right, Tilt Up, Tilt Down, Roll Left, Roll Right`, and each value is a JSON list.
- [ ] Intervals cover the full range of sampled frame indices with no gaps or overlaps.
- [ ] `/root/pred_dyn_masks.npz` loads with `np.load(..., allow_pickle=False)` and contains a `shape` array of length 2 with positive integers.
- [ ] For every sampled frame index `i` referenced by the JSON, all three keys `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr` are present, `indptr` has length `H+1`, `indptr[0] == 0`, `indptr[-1] == len(data) == len(indices)`, and `indices` values are in `[0, W)`.
- [ ] Reconstructing a mask via `csr_matrix((data, indices, indptr), shape=(H,W)).toarray().astype(bool)` yields a boolean array with the declared shape.
- [ ] Sampling rate used is `fps = 5`; the number of sampled frames matches `floor(duration * 5)` (or the chosen consistent convention) and is used consistently across both files.
- [ ] Only the two required output files under `/root/` are created/modified; no unrelated state is touched.
- [ ] Retrieved BigCodeBench examples were used only as generic I/O inspiration; none of their filenames, keys, or schemas leaked into the outputs.
- [ ] On any per-frame failure, a safe fallback (Stay label / empty mask) was emitted so no key is missing.
