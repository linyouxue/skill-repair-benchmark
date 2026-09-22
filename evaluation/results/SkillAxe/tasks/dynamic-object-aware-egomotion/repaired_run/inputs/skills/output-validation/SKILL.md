---
name: output-validation
description: "Local self-check of instructions and mask outputs (format/range/consistency) without using GT."
---

# When to use
- After generating your outputs (interval instructions, masks, etc.), before submission/hand-off.

# Checks
- **Key format**: every key is `"{start}->{end}"`, integers only, `start<end` for half-open intervals.
- **Coverage**:
  - JSON intervals should cover all **sample indices** `[0, K)` exactly (no gaps/overlaps) if you are emitting per-sample labels.
  - Max sample index in JSON should be `K-1` (i.e., max `end` should be `K`).
- **Frame count**: NPZ `f_{i}_*` count equals sampled frame count `K`; no gaps (must have `f_0_* ... f_{K-1}_*`).
- **CSR integrity**: each frame has `data/indices/indptr`; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices within `[0,W)`.
- **Value validity**: JSON values are non-empty string lists; labels in the allowed set.

## Mask quality sanity checks (unsupervised, catches common failures)
These do not require GT but often predict verifier failures:
- **Foreground fraction** per frame: `p = mask.mean()` should not be degenerate across the whole video.
  - Flag if almost all frames have `p < 1e-5` (empty) or `p > 0.5` (nearly full-frame) unless expected.
- **Temporal flicker proxy**: `xor_mean = mean(mask[i] XOR mask[i-1])`.
  - Flag if consistently very high (indicates unstable differencing/thresholding).
- **Connected components sanity**: if you keep many tiny components, your area filter is too weak.

# Reference snippet
```python
import json, numpy as np, cv2
VIDEO_PATH = "<path/to/video>"
INSTRUCTIONS_PATH = "<path/to/interval_instructions.json>"
MASKS_PATH = "<path/to/masks.npz>"

cap=cv2.VideoCapture(VIDEO_PATH)
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); H=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); W=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
cap.release()

j=json.load(open(INSTRUCTIONS_PATH))
npz=np.load(MASKS_PATH)

# JSON format
for k,v in j.items():
    s,e=k.split("->"); assert s.isdigit() and e.isdigit()
    s=int(s); e=int(e); assert 0<=s<e
    assert isinstance(v,list) and len(v)>0
    for lbl in v: assert isinstance(lbl,str)

# NPZ / CSR format
frames=0
while f"f_{frames}_data" in npz: frames+=1
assert frames>0
assert npz["shape"].dtype==np.int32
assert int(npz["shape"][0])==H and int(npz["shape"][1])==W

def csr_to_dense(i):
    indptr=npz[f"f_{i}_indptr"]; indices=npz[f"f_{i}_indices"]
    m=np.zeros((H,W), dtype=bool)
    for r in range(H):
        a=indptr[r]; b=indptr[r+1]
        if b>a:
            m[r, indices[a:b]] = True
    return m

# Quality sanity
m_prev=None
fg_fracs=[]
flick=[]
for i in range(frames):
    m=csr_to_dense(i)
    fg_fracs.append(m.mean())
    if m_prev is not None:
        flick.append(np.logical_xor(m, m_prev).mean())
    m_prev=m

print("fg_frac mean", float(np.mean(fg_fracs)), "min", float(np.min(fg_fracs)), "max", float(np.max(fg_fracs)))
if flick:
    print("flicker mean", float(np.mean(flick)), "p90", float(np.percentile(flick, 90)))
```

# Self-check list
- [ ] JSON keys/values pass format checks.
- [ ] JSON intervals cover the sample index range consistently with half-open semantics.
- [ ] NPZ frame count matches sampling; keys consecutive.
- [ ] CSR structure and `shape` validated.
- [ ] Mask sanity: foreground fraction not degenerate; flicker proxy not extreme.
