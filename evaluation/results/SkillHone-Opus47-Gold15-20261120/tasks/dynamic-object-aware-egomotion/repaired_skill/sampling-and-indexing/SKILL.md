---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so interval instructions and mask frames stay aligned with a valid key/index scheme."
---

# When to use
- You need to decide a sampling stride/FPS and ensure *all downstream outputs* (interval instructions, per-frame artifacts, etc.) cover the same frame range with consistent indices.

# Core steps
- Read video metadata: frame count `total`, native fps, resolution (H, W).
- If a target sampling fps is specified, derive a uniform integer stride:
  `step = max(1, int(round(src_fps / target_fps)))`.
  Prefer this uniform derivation over hand-picking a step; it keeps the inter-sample gap constant so threshold tuning is stable.
- Build `sample_ids = list(range(0, total, step))`. Do **not** append `total-1` as an extra ragged last sample unless the task explicitly asks for it — that breaks the uniform stride and can inflate the final interval.
- The downstream key index `k` refers to a *sampled* frame index `0..len(sample_ids)-1`, **not** the raw video frame index. Interval keys and NPZ `f_{k}_*` must share this same `k` space.
- Interval key format: `"{start}->{end}"`, integers only, with `0 <= start < end <= n_samples`. Document inclusive/exclusive semantics and stay consistent.

# Half-open interval convention (used by this task)
- Keys are half-open `[start, end)`; `"0->1"` labels sampled frame 0 only.
- The set of keys must **partition** `[0, n_samples)`: concatenated ranges cover every sampled index exactly once, with no gap and no overlap. This is the most common silent failure mode — verify it explicitly.
- Equivalently, if `keys` are sorted by `start`, then the first `start == 0`, each next `start == previous end`, and the final `end == n_samples`.

# Pseudocode
```python
import cv2
VIDEO_PATH = "<path/to/video>"
TARGET_FPS = 5  # from the task prompt, if given
cap = cv2.VideoCapture(VIDEO_PATH)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_fps = cap.get(cv2.CAP_PROP_FPS)
H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
step = max(1, int(round(src_fps / TARGET_FPS)))
sample_ids = list(range(0, total, step))
n_samples = len(sample_ids)
# Generate all downstream outputs only for k in 0..n_samples-1
```

# Self-check list
- [ ] `step` derived from `src_fps / target_fps` (not an arbitrary constant) when a target fps is given.
- [ ] `sample_ids` strictly increasing and every id `< total`.
- [ ] Downstream outputs use the sampled index `k` (0..n_samples-1), not the raw frame number.
- [ ] JSON keys are plain `start->end` with `0 <= start < end <= n_samples`.
- [ ] Keys form a partition of the half-open range `[0, n_samples)` (no gap, no overlap, first start 0, last end n_samples).
- [ ] Any per-frame artifact store (e.g., NPZ) contains exactly `f_{k}_*` for `k` in `0..n_samples-1` and no extras.
