---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so interval instructions and mask frames stay aligned with a valid key/index scheme."
---

# When to use
- You need to decide a sampling stride/FPS and ensure *all downstream outputs* (interval instructions, per-frame artifacts, etc.) cover the same frame range with consistent indices.

# Core steps
- Read video metadata: frame count, fps, resolution.
- Choose a sampling strategy (e.g., every 10 frames or target ~10–15 fps) to produce `sample_ids`.
- Decode frames at source indices `sample_ids`, but **write outputs keyed by sampled index** `i=0..num_samples-1` (i.e., the position within `sample_ids`), not by original video frame number.
- Use a strict interval key format `"{start}->{end}"` where **start/end are sampled indices** and the interval is **half-open**: `"a->b"` labels sampled indices `[a, b)` (end-exclusive). This implies the final interval end is commonly `end == num_samples`.

# Pseudocode
```python
import cv2, numpy as np
VIDEO_PATH = "<path/to/video>"
TARGET_FPS = 5  # example
cap=cv2.VideoCapture(VIDEO_PATH)
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_fps=float(cap.get(cv2.CAP_PROP_FPS))

# Source-frame indices to decode (video-frame domain)
duration = (n-1) / max(src_fps, 1e-6)
sample_times = np.arange(0.0, duration + 1e-9, 1.0 / TARGET_FPS)
sample_ids = np.clip(np.round(sample_times * src_fps).astype(int), 0, n-1)
# De-dup in case rounding repeats frames
sample_ids = np.unique(sample_ids).tolist()

# Sampled index domain for outputs is i=0..num_samples-1
num_samples = len(sample_ids)
# JSON intervals must be half-open on sampled indices: "i->i+1" labels sample i.
```

# Self-check list
- [ ] `sample_ids` strictly increasing, all < total frame count.
- [ ] Output coverage max index matches `sample_ids[-1]` (or matches your documented sampling policy).
- [ ] JSON keys are plain `start->end`, no extra text.
- [ ] Any per-frame artifact store (e.g., NPZ) contains exactly the sampled frames and no extras.
