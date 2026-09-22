---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so all downstream artifacts cover the same frames with consistent key conventions."
---

# When to use
- You must produce per-frame artifacts and interval keys that align with a sampling policy (stride or target FPS).

# Core steps
- Read video metadata: frame count, fps, resolution.
- Derive `sample_ids` (strictly increasing, within `[0, n)`) using stride or target FPS.
- Generate **all downstream outputs only for `sample_ids`**; do not mix true frame ids with 0..K counters.
- Use a strict interval key format `"{start}->{end}"` (integers only) and keep a single convention (commonly half-open, `end=start+1` for per-frame labels).

# Code sketch
```python
import cv2

def sample_indices(video_path, target_fps=None, stride=None):
    cap = cv2.VideoCapture(video_path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    if stride is None:
        if target_fps is None or fps <= 0:
            stride = max(1, n // 50)
        else:
            stride = max(1, int(round(fps / target_fps)))
    ids = list(range(0, n, stride))
    if not ids:
        ids = [0]
    return ids, n
```

# Self-check list
- [ ] `sample_ids` strictly increasing, all `< total_frames`.
- [ ] Interval keys are plain `start->end` with consistent convention.
- [ ] Any per-frame store (e.g., NPZ) contains exactly the sampled frame ids.
