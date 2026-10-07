---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so interval instructions and mask frames stay aligned with a valid key/index scheme."
---

# When to use
- You need to decide a sampling stride/FPS and ensure *all downstream outputs* (interval instructions, per-frame artifacts, etc.) cover the same frame range with consistent indices.

# Core steps
- Read video metadata: frame count, fps, resolution.
- When an exact target FPS is requested, sample on one regular time grid beginning at `t=0`. Endpoint inclusion is subordinate to that cadence: never append source frame `n-1` merely to include the physical last frame. Include it only when the regular target-FPS grid selects it.
- Keep the two index spaces separate: `sample_ids[k]` is a source-video frame ID, while `k` is the dense sampled-frame ordinal used by all output keys.
- For `N = len(sample_ids)`, per-frame artifacts must be exactly `f_0 ... f_{N-1}`. Half-open instruction intervals use `0 <= start < end <= N` and must cover sampled ordinals `0 ... N-1` exactly once.

# Pseudocode
```python
import cv2, numpy as np
VIDEO_PATH = "<path/to/video>"
cap=cv2.VideoCapture(VIDEO_PATH)
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_fps=cap.get(cv2.CAP_PROP_FPS)
target_fps=5.0
last_t=(n-1)/src_fps
k_max=int(np.floor(last_t*target_fps+1e-9))
sample_times=np.arange(k_max+1, dtype=float)/target_fps
sample_ids=np.rint(sample_times*src_fps).astype(int)
sample_ids=np.unique(sample_ids[(sample_ids>=0) & (sample_ids<n)]).tolist()
# Do not append n-1 unless it is already selected by this cadence.
N=len(sample_ids)
# Generate downstream keys with ordinals 0..N-1, not source IDs.
```

# Self-check list
- [ ] `sample_ids` strictly increasing, all < total frame count.
- [ ] Consecutive sample times follow the requested cadence; no off-grid endpoint was appended.
- [ ] JSON keys are plain `start->end`, use sampled ordinals, and their half-open intervals cover exactly `0..N-1` with no gap or extra ordinal.
- [ ] Any per-frame artifact store contains exactly `N` consecutive sampled ordinals and no extras.
