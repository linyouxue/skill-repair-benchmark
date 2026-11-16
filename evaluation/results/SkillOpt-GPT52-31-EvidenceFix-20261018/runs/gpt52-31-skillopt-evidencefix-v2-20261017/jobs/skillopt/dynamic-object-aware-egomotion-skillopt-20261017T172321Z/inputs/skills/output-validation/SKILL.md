---
name: output-validation
description: "Local self-check of instructions and mask outputs (format/range/consistency) without using GT."
---

# When to use
- After generating your outputs (interval instructions, masks, etc.), before submission/hand-off.

# Checks
- **Key format**: every key is `"{start}->{end}"`, integers only, `start<=end`.
- **Coverage**: max frame index ≤ video total-1; consistent with your sampling policy.
- **Frame count**: NPZ `f_{i}_*` count equals sampled frame count; no gaps or missing components.

- **Sampling cross-check (fps-derived)**: compute expected sampled source-frame indices from (video_fps, n_frames, sample_fps). Verify:
  - expected sample count == NPZ `f_{i}_*` frame count
  - JSON interval keys cover exactly sample indices `[0, expected_count)` (half-open ranges)
  - max `end` in JSON equals expected_count and there are no gaps/overlaps
  This catches common off-by-one (e.g., 19 vs 18) errors.
- **CSR integrity**: each frame has `data/indices/indptr`; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices within `[0,W)`.
- **Value validity**: JSON values are non-empty string lists; labels in the allowed set.


- **Mask quality (non-GT, lightweight)**:
  - **Foreground coverage** per frame `mask.mean()`; flag near-all-zero for long spans or overly dense masks.
  - **Temporal flicker**: adjacent-frame XOR rate `xor.mean()`; high values indicate instability.
  - **Border activation**: fraction of foreground in a thin border band; high values often means warp/extrapolation artifacts.
  - **Tiny-component dominance**: many small connected components indicates speckle/noise.
# Reference snippet
```python
import json, numpy as np, cv2
VIDEO_PATH = "<path/to/video>"
INSTRUCTIONS_PATH = "<path/to/interval_instructions.json>"
MASKS_PATH = "<path/to/masks.npz>"
cap=cv2.VideoCapture(VIDEO_PATH)
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); H=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); W=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
j=json.load(open(INSTRUCTIONS_PATH))
npz=np.load(MASKS_PATH)
for k,v in j.items():
    s,e=k.split("->"); assert s.isdigit() and e.isdigit()
    s=int(s); e=int(e); assert 0<=s<=e<n
    for lbl in v: assert isinstance(lbl,str)
frames=0
while f"f_{frames}_data" in npz: frames+=1
assert frames>0
assert npz["shape"][0]==H and npz["shape"][1]==W
indptr=npz["f_0_indptr"]; indices=npz["f_0_indices"]
assert indptr.shape[0]==H+1 and indptr[-1]==indices.size
assert indices.size==0 or (indices.min()>=0 and indices.max()<W)
```


# --- fps-derived sampling and coverage checks (no GT) ---
video_fps = float(cap.get(cv2.CAP_PROP_FPS))
sample_fps = 5.0  # set to your required sample rate
step = max(1, int(round(video_fps / sample_fps)))
expected_src_ids = list(range(0, n, step))
expected_samples = len(expected_src_ids)

# JSON interval coverage over sampled indices (half-open)
covered = []
for k in j.keys():
    s,e = map(int, k.split('->'))
    covered.extend(range(s,e))
covered = sorted(covered)
assert covered, 'No intervals in JSON.'
assert covered[0] == 0, f'JSON does not start at sample 0 (starts at {covered[0]}).'
assert covered == list(range(0, max(covered)+1)), 'JSON sample coverage has gaps/overlaps.'
assert (max(covered)+1) == expected_samples, (
    f'JSON covers {max(covered)+1} samples but expected {expected_samples} from fps sampling.'
)
assert frames == expected_samples, (
    f'NPZ has {frames} frames but expected {expected_samples} from fps sampling.'
)

# --- lightweight non-GT mask diagnostics ---
prev_mask = None
area = []
flicker = []
border_act = []
tiny_counts = []
B = 10  # border band width in pixels
border_band = np.zeros((H, W), dtype=bool)
border_band[:B,:] = True; border_band[-B:,:] = True
border_band[:,:B] = True; border_band[:,-B:] = True

for i in range(frames):
    # decode CSR to dense bool for diagnostics
    indptr = npz[f"f_{i}_indptr"]; indices = npz[f"f_{i}_indices"]
    m = np.zeros((H, W), dtype=bool)
    for r in range(H):
        cols = indices[indptr[r]:indptr[r+1]]
        if cols.size:
            m[r, cols] = True

    area.append(float(m.mean()))
    border_act.append(float(m[border_band].mean()))

    ncomp, _, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    if ncomp > 1:
        min_area = max(32, (H * W) // 5000)
        tiny = int((stats[1:, cv2.CC_STAT_AREA] < min_area).sum())
    else:
        tiny = 0
    tiny_counts.append(tiny)

    if prev_mask is not None:
        flicker.append(float(np.logical_xor(m, prev_mask).mean()))
    prev_mask = m

print('[MASK_DIAG] area(min/median/max)=', min(area), float(np.median(area)), max(area))
print('[MASK_DIAG] flicker(mean)=', float(np.mean(flicker)) if flicker else 0.0)
print('[MASK_DIAG] border_act(mean)=', float(np.mean(border_act)))
print('[MASK_DIAG] tiny_cc(median)=', float(np.median(tiny_counts)))

# sanity flags (tune, but keep lightweight)
if max(area) > 0.50:
    print('[WARN] masks too dense (max area > 50%). Likely bad alignment/threshold.')
if flicker and float(np.mean(flicker)) > 0.15:
    print('[WARN] high temporal flicker (mean XOR > 0.15). Add temporal stabilization.')
if float(np.mean(border_act)) > 0.20:
    print('[WARN] strong border activation. Likely warp/extrapolation artifacts; erode valid/crop border.')

# Self-check list
- [ ] JSON keys/values pass format checks.
- [ ] Max frame index within video range and near sampled max.
- [ ] NPZ frame count matches sampling; keys consecutive.
- [ ] CSR structure and `shape` validated.


# Troubleshooting (common failures)
- **NPZ frame count != expected (fps-derived)**: ensure you compute sample indices from `video_fps/sample_fps` with a consistent rounding policy, and that you do *not* add an extra last frame unless it is part of the expected stride list.
- **JSON covers wrong number of samples**: keys are half-open; make sure the last interval ends at `expected_samples` and coverage is contiguous from 0.
- **Masks overly dense** (e.g., max area > 50%): alignment likely failed or threshold too low; tighten threshold floor, improve transform quality checks, or suppress invalid borders.
- **High flicker** (e.g., mean XOR > 0.15): add temporal smoothing/majority vote, smooth transforms before differencing, or increase persistence requirements.
- **High border activation**: erode valid region more, drop border-touching components, or crop a border band from consideration.
- **Many tiny components**: increase minimum component area and apply stronger morphological opening.
