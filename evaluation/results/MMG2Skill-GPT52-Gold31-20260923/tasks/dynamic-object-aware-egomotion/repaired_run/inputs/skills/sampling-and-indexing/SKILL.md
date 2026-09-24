---
name: sampling-and-indexing
description: Sample the video at the required FPS and keep indices consistent so JSON
  intervals and NPZ masks refer to **sample indices** (0..S-1) with half-open ranges.
---

## Steps
1. Read video metadata (`total_frames`, `src_fps`, `H`, `W`) from `/root/input.mp4`.
2. Set `target_fps = 5` and compute a frame stride `step = max(1, int(round(src_fps / target_fps)))`.
3. Create original-frame sample positions: `sample_frame_ids = list(range(0, total_frames, step))`.
4. Define **sample indices** `i = 0..S-1` where `S = len(sample_frame_ids)`. All downstream artifacts (labels, masks) must be stored by this sample index `i` (consecutive starting at 0), not by original frame number.
5. When writing interval keys for motion labels, use half-open **sample-index** ranges: `"{start}->{end}"` covers sampled indices `[start,end)` (so `0->1` means sample 0 only).
6. Ensure the NPZ contains exactly one mask per sampled index `i` (0..S-1), with matching consecutive keys.
## Expected Result
A sampled frame sequence at ~5 fps with a clear mapping from sample index `i` to original video frame id, and all outputs (JSON intervals, NPZ masks) aligned to the same consecutive sample-index timeline `[0,S)`.
