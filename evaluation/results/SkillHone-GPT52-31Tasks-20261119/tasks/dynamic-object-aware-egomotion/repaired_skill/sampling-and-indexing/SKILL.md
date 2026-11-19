---
name: sampling-and-indexing
description: "Standardize video sampling and indexing so interval instructions and per-sampled-frame outputs stay aligned (sample-index space, half-open ranges)."
---

# When to use
- You must sample a video at a target FPS and ensure **all downstream outputs** (interval instructions, per-frame masks, etc.) refer to the **same sampled frames**.

# Key conventions (do not skip)
The most common failure mode is mixing up **source video frame indices** with **sample indices**.

- `sample_frame_ids`: the list of frame numbers pulled from the original video (e.g., `[0, 12, 24, ...]`).
- `S = len(sample_frame_ids)`: number of sampled frames.
- **All task outputs are keyed by sample index** `i = 0..S-1`:
  - Instructions JSON keys are `"{start}->{end}"` where `start,end` are **sample indices**.
  - Mask NPZ keys are `f_{i}_data / f_{i}_indices / f_{i}_indptr` where `i` is a **sample index**.

## Half-open interval requirement
Intervals are **half-open** ranges on the **sample index axis**:
- Key `"0->1"` labels sampled frame **0 only**.
- Therefore every interval must satisfy: `0 <= start < end <= S`.
- The interval set should form a partition of `[0, S)` (no gaps, no overlaps), so the last interval should end at `S`.

# Sampling at a target FPS
Prefer a deterministic policy tied to the video FPS. Two common options:

## Option A: fixed frame-step (simple and deterministic)
```python
step = max(1, int(round(src_fps / target_fps)))
sample_frame_ids = list(range(0, n_frames, step))
```

## Option B: time-grid (handles non-integer FPS better)
```python
# k = 0,1,2,...
t = k / target_fps
frame_id = int(round(t * src_fps))
```
Deduplicate collisions (when rounding hits the same frame twice) and keep order; stop once `frame_id >= n_frames`.

**Note:** Do not append the last frame unless the task explicitly requests it; doing so changes the sampling schedule.

# Pseudocode
```python
import cv2

def compute_sample_frame_ids(video_path: str, target_fps: float):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()

    step = max(1, int(round(src_fps / target_fps)))
    sample_frame_ids = list(range(0, n_frames, step))

    # sample indices are 0..S-1
    return sample_frame_ids, src_fps, n_frames
```

# Self-check list
- [ ] `sample_frame_ids` is strictly increasing and every id is in `[0, n_frames)`.
- [ ] `S = len(sample_frame_ids)`.
- [ ] You produce **exactly** `S` masks: `f_0_*` through `f_{S-1}_*`.
- [ ] JSON instructions use **sample indices**, and intervals are half-open and partition `[0, S)`:
  - first start is `0`
  - each interval start equals previous end
  - last end equals `S`
