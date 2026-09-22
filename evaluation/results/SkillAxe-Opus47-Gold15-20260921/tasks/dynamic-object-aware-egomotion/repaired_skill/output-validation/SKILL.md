---
name: output-validation
description: "Local self-check of instructions and mask outputs (format/range/consistency/plausibility) without using GT."
---

# When to use
- After generating your outputs (interval instructions, masks, etc.), before submission/hand-off.

# Checks
- **Key format**: every key is `"{start}->{end}"`, integers only, `start<end`.
- **Coverage**: max frame index ≤ video total-1; consistent with your sampling policy. Intervals should form a partition of the sampled range with no gaps or overlaps if the task expects full coverage.
- **Frame count**: NPZ `f_{i}_*` count equals sampled frame count; no gaps or missing components.
- **CSR integrity**: each frame has `data/indices/indptr`; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices within `[0,W)`; `data.size == indices.size`.
- **Value validity**: JSON values are non-empty string lists; labels in the allowed set.
- **Mask plausibility (content, not just structure)**: reconstruct each mask and compute `fg_frac = nnz / (H*W)`.
  - Warn/re-tune if the **mean** `fg_frac` across frames is `> 0.15` (masks are flooded — global motion likely not compensated; parallax or wrong transform model).
  - Warn/re-tune if the mean is `< 0.001` on a scene that clearly contains motion (thresholds too aggressive or min-area too large).
  - Warn if a single frame has `fg_frac > 0.4` (almost the entire image marked dynamic).
  Structural checks alone do NOT catch these failure modes; both flooded and empty masks pass CSR/format checks but score near-zero IoU.

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
    s=int(s); e=int(e); assert 0<=s<e<=n
    assert isinstance(v,list) and len(v)>0
    for lbl in v: assert isinstance(lbl,str)
frames=0
while f"f_{frames}_data" in npz: frames+=1
assert frames>0
assert npz["shape"][0]==H and npz["shape"][1]==W

fg_fracs=[]
for i in range(frames):
    indptr=npz[f"f_{i}_indptr"]; indices=npz[f"f_{i}_indices"]; data=npz[f"f_{i}_data"]
    assert indptr.shape[0]==H+1 and indptr[-1]==indices.size==data.size
    assert indices.size==0 or (indices.min()>=0 and indices.max()<W)
    fg_fracs.append(indices.size/float(H*W))
import statistics
mean_fg=statistics.fmean(fg_fracs)
max_fg=max(fg_fracs)
print(f"fg_frac mean={mean_fg:.4f} max={max_fg:.4f}")
# Plausibility thresholds — treat as hard warnings before submitting.
assert mean_fg <= 0.15, "Masks flooded; global motion likely not compensated (try homography, blur, raise threshold)."
assert max_fg  <= 0.40, "At least one frame's mask covers >40% of the image — almost certainly a failure."
# If the scene has moving objects, also expect mean_fg to be well above 0 (e.g. > 1e-4).
```

# Self-check list
- [ ] JSON keys/values pass format checks; intervals partition the sampled range as required.
- [ ] Max frame index within video range and near sampled max.
- [ ] NPZ frame count matches sampling; keys consecutive.
- [ ] CSR structure and `shape` validated.
- [ ] Mask foreground-fraction distribution is plausible (not near 0 on active scenes, not near 1 anywhere).
