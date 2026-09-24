---
name: dyn-object-masks
description: Generate per-sampled-frame dynamic-object binary masks (motion-compensated)
  and save them in CSR sparse format to an NPZ.
---

## Steps
1. For each sampled frame index `i` (0..S-1), read/compute `curr_gray` (H×W).
2. For `i==0`, set the dynamic mask to all-False (no previous frame to compare), and encode/save it.
3. For `i>0`, **global alignment**: warp `prev_gray` into the current frame using the estimated transform `M_{i-1→i}` (affine or homography).
4. Compute a **valid region** by warping an all-ones mask with the same transform; only score differences where `valid==True` to avoid border fill artifacts.
5. Compute `diff = abs(curr_gray - warped_prev_gray)` and choose a robust threshold from `diff[valid]` (e.g., `median + 3×MAD`, with a minimum floor to avoid noise).
6. Build a raw foreground: `raw = (diff > thr) & valid`, then postprocess with morphology (open then close).
7. Remove small connected components (area threshold) to suppress flicker/noise.
8. **CSR encoding (True pixels only)** for final `mask` (bool, H×W):
   - `rows, cols = np.nonzero(mask)`
   - `indices = cols.astype(np.int32)`
   - `data = np.ones(indices.size, dtype=np.uint8)`
   - `counts = np.bincount(rows, minlength=H).astype(np.int32)`
   - `indptr = np.concatenate([[0], np.cumsum(counts)]).astype(np.int32)`
   - Store keys `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr`
9. Store `shape = np.array([H, W], dtype=np.int32)` once in the NPZ and write `/root/pred_dyn_masks.npz`.
## Expected Result
`/root/pred_dyn_masks.npz` contains `shape=[H,W]` and, for every sampled frame index `i`, valid CSR triplets `f_{i}_data/indices/indptr` that represent the binary dynamic mask for that sampled frame.
