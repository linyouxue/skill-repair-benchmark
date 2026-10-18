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


- **Mask area ratio**: monitor per-frame foreground coverage (`mask.mean()`). Flag masks that are nearly empty for long spans or suddenly jump to very large coverage.
- **Temporal flicker**: compute adjacent-frame XOR rate (`xor.mean()`) to detect unstable dynamic masks and threshold oscillation.
- **Connected components**: track number of components and reject outputs dominated by many tiny blobs/noise speckles.
- **Boundary coherence**: inspect contour smoothness/perimeter-to-area ratio or edge continuity; highly jagged masks often indicate poor motion compensation.
- **Warp-border contamination**: after camera-motion warping, measure activation in a thin image border band; heavy border activation often signals invalid flow/homography regions.
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


# lightweight non-GT mask quality diagnostics
prev_mask=None
area_ratios=[]; flickers=[]; border_rates=[]; component_counts=[]
for i in range(frames):
    mask=np.zeros((H,W),dtype=bool)
    indptr=npz[f"f_{i}_indptr"]
    indices=npz[f"f_{i}_indices"]
    for r in range(H):
        cols=indices[indptr[r]:indptr[r+1]]
        mask[r,cols]=True

    area=float(mask.mean())
    area_ratios.append(area)

    ncomp, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    small=(stats[1:,cv2.CC_STAT_AREA] < max(32, (H*W)//5000)).sum() if ncomp>1 else 0
    component_counts.append((ncomp-1, int(small)))

    border=10
    border_band=np.zeros_like(mask, dtype=bool)
    border_band[:border,:]=True; border_band[-border:,:]=True
    border_band[:,:border]=True; border_band[:,-border:]=True
    border_rates.append(mask[border_band].mean())

    if prev_mask is not None:
        flickers.append(np.logical_xor(mask, prev_mask).mean())
    prev_mask=mask

print('area ratio range', np.min(area_ratios), np.max(area_ratios))
print('avg flicker', np.mean(flickers) if flickers else 0.0)
print('avg border activation', np.mean(border_rates))
print('example component stats', component_counts[:3])

# Self-check list
- [ ] JSON keys/values pass format checks.
- [ ] Max frame index within video range and near sampled max.
- [ ] NPZ frame count matches sampling; keys consecutive.
- [ ] CSR structure and `shape` validated. 

- [ ] Foreground area ratios stay within a plausible range and do not oscillate sharply.
- [ ] Adjacent-mask XOR flicker is low enough to avoid frame-to-frame instability.
- [ ] Masks are not dominated by tiny disconnected components or border artifacts.
- [ ] Boundary shapes appear coherent after morphology/filtering.


# Retuning guidance
- If masks are too sparse or IoU is low, relax motion thresholds slightly, reduce over-aggressive erosion, or lower minimum motion magnitude.
- If masks are overly dense or include static background, tighten residual thresholds, strengthen morphology opening, or increase minimum component area.
- If temporal XOR flicker is high, smooth flow/residual estimates across frames, stabilize homography estimation, or add temporal consistency filtering.
- If border-band activation is consistently high, crop invalid warp margins or suppress detections near extrapolated regions.
