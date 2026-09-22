---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so interval instructions and mask frames stay aligned with a valid key/index scheme."
---

# When to use
- You need to decide a sampling stride/FPS and ensure *all downstream outputs* (interval instructions, per-frame artifacts, etc.) cover the same frame range with consistent indices.

# Core steps
- Read video metadata: frame count, fps, resolution.
- Choose a sampling strategy to produce sampled frames at the **requested sample rate** (e.g., fps = 5).
- **Define two index spaces and don’t mix them**:
  1) **Source frame index**: the original video frame number in `[0, total_frames)`.
  2) **Sample index**: position in the sampled sequence, in `[0, K)`.
- For tasks that specify keys like `"0->1"` where `0` is the **start sample index**, your JSON intervals must be over **sample indices**, not source frame indices.
- Masks NPZ keys `f_{i}_*` must also use the same **sample index** `i`.

# Recommended sampling for target FPS
- Prefer timestamp-based sampling to match a target FPS even when source FPS is different:
  - Let `t_k = k / target_fps` for `k=0..K-1` up to video duration.
  - Map to source frame via `src = round(t_k * src_fps)`, then clamp to `[0, total_frames-1]`.
  - Deduplicate if rounding hits the same frame; keep order.

# Pseudocode
```python
import cv2, numpy as np
VIDEO_PATH = "<path/to/video>"
cap=cv2.VideoCapture(VIDEO_PATH)
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_fps=float(cap.get(cv2.CAP_PROP_FPS))

TARGET_FPS=5.0

duration = n/src_fps
sample_times = np.arange(0.0, duration, 1.0/TARGET_FPS)
raw = np.round(sample_times * src_fps).astype(int)
raw = np.clip(raw, 0, n-1)

# sample_ids are SOURCE frame indices (for reading)
sample_ids=[]
seen=set()
for idx in raw.tolist():
    if idx not in seen:
        sample_ids.append(idx)
        seen.add(idx)

# Downstream outputs are indexed by SAMPLE index i=0..K-1
# i maps to source frame sample_ids[i]
```

# Interval key conventions
- Use a strict interval key format `"{start}->{end}"` where **end is exclusive** (half-open range).
- If your per-sample motion labels are `labels[i]` for sample index `i`, then a single-frame interval is `"i->i+1"`.

# Self-check list
- [ ] `sample_ids` strictly increasing (or at least non-decreasing before dedup), all < total frame count.
- [ ] You maintain and can print the mapping: `sample index i -> source frame sample_ids[i]`.
- [ ] Output coverage: JSON intervals cover exactly the sample index range `[0, K)` with half-open keys.
- [ ] NPZ contains exactly `K` frames with consecutive keys `f_0_* ... f_{K-1}_*`.
- [ ] JSON keys are plain `start->end`, no extra text.
