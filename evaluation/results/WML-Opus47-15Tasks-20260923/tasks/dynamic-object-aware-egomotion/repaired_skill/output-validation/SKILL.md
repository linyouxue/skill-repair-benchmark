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
- **CSR integrity**: each frame has `data/indices/indptr`; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices within `[0,W)`.
- **Value validity**: JSON values are non-empty string lists; labels in the allowed set.

## Payload plausibility (additive; not a correctness proof)
Format checks alone will accept degenerate payloads (all-empty masks, all-full masks, wildly inconsistent frame-to-frame outputs). For per-frame mask/label artifacts, also compute cheap self-consistency statistics and use them as *retry triggers*, not as ground-truth assertions:
- **Foreground-fraction distribution**: per-frame nnz / (H·W). Flag if the mean falls outside a documented band for the task, or if any individual frame is ~0% or near-saturated (e.g., ≥ ~40%) when neither extreme is expected.
- **Empty-frame ratio**: fraction of frames with nnz == 0. Flag when a non-trivial share of frames is empty in a scene where motion labels other than `Stay` are present.
- **Temporal flicker**: mean of `logical_xor(mask_i, mask_{i-1}).mean()` across consecutive sampled frames. Flag unusually high values (masks that flip most of their pixels every frame).
- **Cross-artifact consistency**: if the motion-label stream contains non-`Stay` labels for a span but the corresponding mask frames are all empty (or vice versa), flag the mismatch.

If any plausibility signal fires, do **not** ship. Route back to the method-selection/tuning step in the producing skill (e.g., `dyn-object-masks` *Method selection & tuning order*) and re-run.

### Scope and non-goals
- Plausibility bands are self-consistency triggers for retry; they are *not* equality assertions against unknown ground truth and must not be turned into hard pass/fail rules pretending to score correctness.
- Do not modify or weaken the schema/format checks above; plausibility checks are strictly additive.

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

# Payload plausibility (retry triggers, not correctness assertions)
HW = float(H*W)
fracs, prev = [], None
flicker = []
for i in range(frames):
    ip = npz[f"f_{i}_indptr"]; idx = npz[f"f_{i}_indices"]
    nnz = int(ip[-1])
    fracs.append(nnz / HW)
    # dense reconstruction only for flicker; skip if memory-bound
    m = np.zeros((H, W), dtype=bool)
    for r in range(H):
        a, b = ip[r], ip[r+1]
        if b > a: m[r, idx[a:b]] = True
    if prev is not None:
        flicker.append(float(np.logical_xor(m, prev).mean()))
    prev = m
empty_ratio = sum(1 for f in fracs if f == 0) / max(1, len(fracs))
mean_frac = float(np.mean(fracs)) if fracs else 0.0
mean_flicker = float(np.mean(flicker)) if flicker else 0.0
# Compare mean_frac, empty_ratio, mean_flicker against the task's documented band and
# trigger a retry (not an assertion failure) if any is out of range.
```

# Self-check list
- [ ] JSON keys/values pass format checks.
- [ ] Max frame index within video range and near sampled max.
- [ ] NPZ frame count matches sampling; keys consecutive.
- [ ] CSR structure and `shape` validated.
- [ ] Payload plausibility computed: foreground-fraction distribution, empty-frame ratio, and temporal flicker are all inside the documented band, and mask activity is consistent with the motion-label stream. If not, route back to the producing skill and retry before submission.
