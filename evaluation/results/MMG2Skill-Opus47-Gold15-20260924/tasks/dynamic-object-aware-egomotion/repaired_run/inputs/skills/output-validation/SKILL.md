---
name: output-validation
description: "Local self-check of instructions and mask outputs (format/range/consistency) without using GT."
---

# When to use
- After generating your outputs (interval instructions, masks, etc.), before submission/hand-off.
# Checks
- **Key format**: every key is `"{start}->{end}"`, integers only, `start<end` for half-open ranges.
- **Partition**: intervals must tile `[0, n_samples)` exactly — no gaps, no overlaps.
- **Coverage**: max frame index ≤ video total-1; consistent with your sampling policy.
- **Frame count**: NPZ `f_{i}_*` count equals sampled frame count; no gaps or missing components; frame 0 present even if empty.
- **CSR integrity**: each frame has `data/indices/indptr`; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices within `[0,W)`.
- **Value validity**: JSON values are non-empty string lists; labels in the allowed set (Stay, Dolly In, Dolly Out, Pan Left, Pan Right, Tilt Up, Tilt Down, Roll Left, Roll Right).
# Reference snippet
```python
import json, numpy as np, cv2
VIDEO_PATH = "<path/to/video>"
INSTRUCTIONS_PATH = "<path/to/interval_instructions.json>"
MASKS_PATH = "<path/to/masks.npz>"
ALLOWED = {"Stay","Dolly In","Dolly Out","Pan Left","Pan Right",
           "Tilt Up","Tilt Down","Roll Left","Roll Right"}
cap=cv2.VideoCapture(VIDEO_PATH)
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); H=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); W=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
j=json.load(open(INSTRUCTIONS_PATH))
covered=[]
for k,v in j.items():
    s,e=k.split("->"); s=int(s); e=int(e); assert s<e
    covered.append((s,e))
    for lbl in v: assert lbl in ALLOWED
covered.sort()
for i,(s,e) in enumerate(covered):
    if i==0: assert s==0
    else: assert s==covered[i-1][1]
npz=np.load(MASKS_PATH)
frames=0
while f"f_{frames}_data" in npz: frames+=1
assert frames == covered[-1][1]
assert npz["shape"][0]==H and npz["shape"][1]==W
for i in range(frames):
    indptr=npz[f"f_{i}_indptr"]; indices=npz[f"f_{i}_indices"]
    assert indptr.shape[0]==H+1 and indptr[-1]==indices.size
    assert indices.size==0 or (indices.min()>=0 and indices.max()<W)
```
# Self-check list
- [ ] JSON keys/values pass format checks and labels are in the allowed set.
- [ ] Intervals form a half-open partition of `[0, n_samples)`.
- [ ] NPZ frame count matches sampled max; keys consecutive from f_0.
- [ ] CSR structure and `shape` validated.
