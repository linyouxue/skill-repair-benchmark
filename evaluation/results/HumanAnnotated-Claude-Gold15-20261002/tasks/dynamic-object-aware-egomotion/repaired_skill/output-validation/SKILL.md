---
name: output-validation
description: "Local self-check of instructions and mask outputs (format/range/consistency) without using GT."
---

# When to use
- After generating your outputs (interval instructions, masks, etc.), before submission/hand-off.

# Checks
- **Key format**: every key is `"{start}->{end}"`, integers only, `start<end`.
- **Expected sample count**: independently reconstruct the regular time grid requested by `target_fps` from source frame count/FPS. Do not append a physical endpoint that is off this grid.
- **Coverage**: for `N_expected` sampled frames, sorted half-open JSON intervals must cover dense sampled ordinals `0..N_expected-1` exactly once and satisfy `0 <= start < end <= N_expected`. Do not use source-video frame IDs as interval keys or bounds.
- **Frame count**: NPZ keys must be exactly `f_0_* ... f_{N_expected-1}_*`, with no gaps, missing components, or extra frame.
- **CSR integrity**: each frame has `data/indices/indptr`; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices within `[0,W)`.
- **Value validity**: JSON values are non-empty string lists; labels in the allowed set.

# Reference snippet
```python
import json, numpy as np, cv2
VIDEO_PATH = "<path/to/video>"
INSTRUCTIONS_PATH = "<path/to/interval_instructions.json>"
MASKS_PATH = "<path/to/masks.npz>"
cap=cv2.VideoCapture(VIDEO_PATH)
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); src_fps=cap.get(cv2.CAP_PROP_FPS)
H=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); W=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
target_fps=5.0
last_t=(n-1)/src_fps
k_max=int(np.floor(last_t*target_fps+1e-9))
sample_times=np.arange(k_max+1, dtype=float)/target_fps
sample_ids=np.rint(sample_times*src_fps).astype(int)
sample_ids=np.unique(sample_ids[(sample_ids>=0) & (sample_ids<n)])
N_expected=len(sample_ids)
j=json.load(open(INSTRUCTIONS_PATH))
npz=np.load(MASKS_PATH)
covered=[]
for k,v in sorted(j.items(), key=lambda kv: int(kv[0].split("->")[0])):
    s,e=k.split("->"); assert s.isdigit() and e.isdigit()
    s=int(s); e=int(e); assert 0<=s<e<=N_expected
    covered.extend(range(s,e))
    for lbl in v: assert isinstance(lbl,str)
assert covered==list(range(N_expected))
frames=0
while f"f_{frames}_data" in npz: frames+=1
assert frames==N_expected
assert not any(k.startswith(f"f_{N_expected}_") for k in npz.files)
assert npz["shape"][0]==H and npz["shape"][1]==W
indptr=npz["f_0_indptr"]; indices=npz["f_0_indices"]
assert indptr.shape[0]==H+1 and indptr[-1]==indices.size
assert indices.size==0 or (indices.min()>=0 and indices.max()<W)
```

# Self-check list
- [ ] JSON keys/values pass format checks.
- [ ] Half-open JSON intervals cover exactly dense sampled ordinals `0..N_expected-1`; the final interval boundary may equal `N_expected`.
- [ ] The independently reconstructed fixed-FPS grid contains no appended off-grid endpoint.
- [ ] NPZ frame count equals `N_expected`; keys are consecutive with no extra frame.
- [ ] CSR structure and `shape` validated. 
