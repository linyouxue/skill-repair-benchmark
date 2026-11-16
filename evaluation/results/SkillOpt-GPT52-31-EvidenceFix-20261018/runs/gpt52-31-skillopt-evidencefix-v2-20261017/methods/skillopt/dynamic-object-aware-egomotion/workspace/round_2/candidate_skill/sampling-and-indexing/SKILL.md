---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so interval instructions and mask frames stay aligned with a valid key/index scheme."
---

# When to use
- You need to decide a sampling stride/FPS and ensure *all downstream outputs* (interval instructions, per-frame artifacts, etc.) cover the same frame range with consistent indices.

# Core steps
- Read video metadata: frame count, fps, resolution.
- Choose a sampling strategy and document it. For **target-fps sampling**, treat it as a deterministic **time grid**:

- For target-fps sampling, record (in code comments/logs) `fps_src`, `target_fps`, `duration`, and the resulting `sample_ids` length to make the sample count auditable.
- Ensure downstream index space is the **sample index** (0..len(sample_ids)-1) and not the raw source frame index unless explicitly required by the task.
  - Let `dt = 1/target_fps`.
  - Generate sample timestamps `t_k = k*dt` for `k = 0..K-1` while `t_k < duration` where `duration = n/fps_src`.
  - Map each timestamp to a source frame index with a single rule (recommend **floor**): `idx_k = min(n-1, floor(t_k * fps_src))`.
  - Deduplicate any repeated `idx_k` (can happen when `target_fps > fps_src`).
  - **Do not append** the last frame unless it is already selected by the time grid/mapping.
- Only produce instructions and masks for `sample_ids`; the max index must be `< total_frames`.
- Use a strict interval key format such as `"{start}->{end}"` (integers only). Decide (and document) whether `end` is inclusive or exclusive, and be consistent.

# Pseudocode
```python
import cv2, math
VIDEO_PATH = "<path/to/video>"
cap = cv2.VideoCapture(VIDEO_PATH)
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps_src = float(cap.get(cv2.CAP_PROP_FPS))

target_fps = 5.0
# Deterministic time-grid sampling
if fps_src <= 0 or n <= 0:
    raise ValueError("bad video metadata")

duration = n / fps_src
k_max = int(math.ceil(duration * target_fps))  # t_k < duration
sample_ids = []
for k in range(k_max):
    t = k / target_fps
    if t >= duration:
        break
    idx = int(math.floor(t * fps_src))
    idx = min(n - 1, max(0, idx))
    if not sample_ids or idx != sample_ids[-1]:
        sample_ids.append(idx)

# IMPORTANT: do not append n-1 unless it was selected above.
# Generate ALL downstream outputs only for sample_ids, and produce exactly len(sample_ids) artifacts.
```

# Self-check list
- [ ] `sample_ids` strictly increasing, all < total frame count.
- [ ] Output coverage max index matches `sample_ids[-1]` (or matches your documented sampling policy).
- [ ] JSON keys are plain `start->end`, no extra text.

- [ ] For target-fps sampling: sample count equals the computed time-grid count (no unconditional `append(n-1)`).
- [ ] All downstream artifacts align **exactly** to the sampled-frame count:
  - JSON intervals reference sample indices only (0..S) and cover exactly `S = len(sample_ids)` frames (e.g., keys like `i->i+1` for per-frame labels).
  - NPZ contains exactly `S` masks (`f_0_*` ... `f_{S-1}_*`) and **no extra frames**.

## Example (count/indices)
If `fps_src=60`, `n=207` ⇒ `duration=3.45s`. With `target_fps=5`, timestamps are `t=0.0,0.2,...,3.4` (18 samples). Using `floor(t*60)` yields indices:
`[0,12,24,36,48,60,72,84,96,108,120,132,144,156,168,180,192,204]` (18 frames). Do **not** append 206, because it is not on the 5fps grid.
- [ ] Any per-frame artifact store (e.g., NPZ) contains exactly the sampled frames and no extras.
