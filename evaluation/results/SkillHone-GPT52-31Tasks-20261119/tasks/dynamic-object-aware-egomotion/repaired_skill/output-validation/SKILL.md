---
name: output-validation
description: "Local self-check of interval instructions and per-sampled-frame CSR masks (format/range/consistency), without using GT."
---

# When to use
- After generating your outputs (interval instructions JSON + CSR-mask NPZ), before handing off.

# Key concepts (critical)
These tasks almost always index outputs by **sample index**, not by original video frame number.

- Let `sample_frame_ids` be the original-video frame numbers you sampled (e.g., `[0, 12, 24, ...]`).
- Let `S = len(sample_frame_ids)` be the number of sampled frames.
- All outputs are keyed by **sample index** `i = 0..S-1`.

## Half-open intervals
Instruction keys `"{start}->{end}"` are **half-open ranges** on sample indices:
- `"0->1"` labels sampled frame 0 only.
- Every interval must satisfy: `0 <= start < end <= S`.
- The set of intervals should partition `[0, S)` (no gaps, no overlaps), so the last interval ends at `S`.

# Validation checks
## JSON (pred_instructions)
- **Key format**: each key is exactly `"<int>-><int>"`.
- **Half-open validity**: `0 <= start < end <= S`.
- **Partition**: after sorting by `start`,
  - first interval starts at `0`
  - each interval start equals the previous interval end
  - last interval ends at `S`
- **Values**:
  - value is a non-empty list of strings
  - every label is in the allowed set from the prompt
  - (optional) if the prompt implies single-label, enforce `len(value)==1`

## NPZ (pred_dyn_masks)
- **Shape**: `npz["shape"] == [H, W]` (prefer `int32`).
- **Frame keys**: for every `i=0..S-1`, NPZ contains all 3 keys:
  - `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr`
- **CSR integrity (per frame)**:
  - `indptr.shape == (H+1,)`
  - `indptr[0] == 0`
  - `indptr` is non-decreasing
  - `indptr[-1] == indices.size == data.size`
  - indices are within `[0, W)`
  - recommended dtypes: `indptr/indices=int32`, `data=uint8` (or `bool`)

### Optional sanity diagnostics (GT-free, catches common quality failures)
These checks do **not** require ground truth but often predict downstream accuracy issues:

- **Per-frame foreground fraction**: `frac_i = nnz_i / (H*W)`.
  - If `frac_i` is ~0 for almost all frames, you are likely under-detecting dynamics (threshold too strict, or global motion fit is being hijacked by a moving object so the mover looks “static”).
  - If `frac_i` is very large for many frames, you are likely mis-estimating global motion (background becomes “dynamic”) or your residual threshold is too loose.

  Practical tuning loop (GT-free):
  - target a *small but non-trivial* median `frac_i` (often < a few percent for typical videos)
  - if median `frac_i` is ~0 → decrease the MAD multiplier or decrease a minimum-residual floor
  - if median `frac_i` is huge → increase the MAD multiplier and/or enable conditional appearance confirmation when raw masks are implausibly large

- **Frame-alignment sanity**:
  - If you compute optical flow `prev -> curr`, remember residual masks are aligned to the **source (`prev`) frame grid**.
  - Ensure your pipeline produces a mask for **every** sample index `i=0..S-1` without forcing `mask[0]` empty unless the prompt explicitly allows it.

- **Temporal consistency** (lightweight):
  - compute overlap between consecutive masks (IoU or intersection/union);
  - a near-zero overlap for every step can signal flicker/threshold issues **or** that you are only capturing transient edge noise.
  - if IoU is always near 1.0 with very large masks, you may be marking stabilized background as dynamic (bad global motion).

- **Degenerate motion label check**:
  - If the instruction JSON collapses to a *single interval covering all frames* with a non-`Stay` label, double-check your dolly/roll evidence gating and pan/tilt sign conventions.
  - If every label is `Stay` but masks show large dynamics, your egomotion threshold may be too strict.

- **Mask distribution sanity**:
  - If early frames are always empty while later frames are large (or vice versa), verify your forward/backward mask alignment and whether you are accidentally storing only one direction.
  - If the median foreground fraction is high but the minimum is near zero, consider adding appearance confirmation (intersection) or tightening the residual threshold.

# Reference snippet (drop-in)
```python
import json
import re
import numpy as np
import cv2

ALLOWED = {
    "Stay",
    "Dolly In",
    "Dolly Out",
    "Pan Left",
    "Pan Right",
    "Tilt Up",
    "Tilt Down",
    "Roll Left",
    "Roll Right",
}

VIDEO_PATH = "/path/to/video.mp4"
INSTRUCTIONS_PATH = "/path/to/pred_instructions.json"
MASKS_PATH = "/path/to/pred_dyn_masks.npz"

# Video metadata (optional but recommended)
cap = cv2.VideoCapture(VIDEO_PATH)
assert cap.isOpened()
H_v = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
W_v = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
cap.release()

j = json.load(open(INSTRUCTIONS_PATH, "r", encoding="utf-8"))
npz = np.load(MASKS_PATH)

shape = npz["shape"]
H, W = int(shape[0]), int(shape[1])
assert (H, W) == (H_v, W_v)

# Count sampled frames S from NPZ keys (expects contiguous 0..S-1)
S = 0
while f"f_{S}_indptr" in npz:
    S += 1
assert S > 0

# NPZ structural checks
for i in range(S):
    for suf in ("data", "indices", "indptr"):
        assert f"f_{i}_{suf}" in npz

    data = npz[f"f_{i}_data"]
    indices = npz[f"f_{i}_indices"]
    indptr = npz[f"f_{i}_indptr"]

    assert indptr.shape == (H + 1,)
    assert int(indptr[0]) == 0
    assert np.all(indptr[:-1] <= indptr[1:])
    nnz = int(indptr[-1])
    assert nnz == indices.size == data.size

    if indices.size:
        assert indices.min() >= 0 and indices.max() < W

# JSON interval checks (sample-index space)
intervals = []
for k, v in j.items():
    m = re.fullmatch(r"(\d+)->(\d+)", k)
    assert m, f"Bad key: {k}"
    s, e = map(int, m.groups())
    assert 0 <= s < e <= S

    assert isinstance(v, list) and len(v) > 0
    assert all(isinstance(lbl, str) for lbl in v)
    assert all(lbl in ALLOWED for lbl in v)

    intervals.append((s, e))

intervals.sort()
assert intervals and intervals[0][0] == 0
for (s, e), (ns, ne) in zip(intervals, intervals[1:]):
    assert ns == e, f"Gap/overlap: {s}->{e} then {ns}->{ne}"
assert intervals[-1][1] == S
```

# Self-check list
- [ ] JSON uses sample indices; intervals are half-open and partition `[0, S)`.
- [ ] Every interval has at least one allowed label.
- [ ] NPZ contains exactly `S` CSR masks and `shape == [H, W]`.
- [ ] CSR arrays are internally consistent for every `i`.
