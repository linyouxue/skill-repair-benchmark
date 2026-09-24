---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so interval instructions and mask frames stay aligned with a valid key/index scheme."
---

# When to use
- You need to decide a sampling stride/FPS and ensure *all downstream outputs* (interval instructions, per-frame artifacts, etc.) cover the same frame range with consistent indices.
# Core steps
- Read video metadata: frame count, source fps, resolution.
- Compute step for a target sampling rate: `step = max(1, round(src_fps / target_fps))` (e.g. src_fps=60, target=5 → step=12).
- Build `sample_ids = list(range(0, n, step))`; do NOT append `n-1` if that would break the uniform-stride assumption — the interval keys index into `sample_ids`, not raw video frames.
- Interval keys are indices into `sample_ids` (0-based), half-open: `"0->1"` labels sampled frame 0 only. The full partition spans `[0, len(sample_ids))`.
- Produce instructions and per-frame masks only for `sample_ids`, and use the sampled-index positions as keys.
# Pseudocode
```python
import cv2
VIDEO_PATH = "/root/input.mp4"
cap=cv2.VideoCapture(VIDEO_PATH)
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_fps=cap.get(cv2.CAP_PROP_FPS)
target_fps=5
step=max(1, round(src_fps/target_fps))
sample_ids=list(range(0, n, step))
n_samples=len(sample_ids)
# Interval JSON keys and NPZ f_{i}_* both use i in [0, n_samples).
```
# Self-check list
- [ ] `sample_ids` strictly increasing, all `< n`.
- [ ] JSON interval keys are indices into `sample_ids`, forming a half-open partition of `[0, n_samples)`.
- [ ] NPZ has exactly `n_samples` frames, keyed `f_0 .. f_{n_samples-1}`.
- [ ] Sampling rate matches the task-specified fps (e.g. fps=5).
