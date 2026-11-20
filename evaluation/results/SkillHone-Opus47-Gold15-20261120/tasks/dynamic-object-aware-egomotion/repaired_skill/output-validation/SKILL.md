---
name: output-validation
description: "Local self-check of instructions and mask outputs (format/range/consistency) without using GT."
---

# When to use
- After generating your outputs (interval instructions, masks, etc.), before submission/hand-off.

# Checks
- **Key format**: every key is `"{start}->{end}"`, integers only, `start < end` (half-open), both within `[0, n_samples]`.
- **Partition / coverage** (half-open): sort keys by `start`; first `start == 0`; each next `start == previous end`; final `end == n_samples`. This catches the common silent failure where intervals leave a gap at the front/back or overlap.
- **Label set**: every entry is a non-empty list of strings from the allowed label set.
- **NPZ frame count**: the count of `f_{k}_*` keys equals `n_samples` and covers `k = 0..n_samples-1` with no gaps and no extras.
- **CSR integrity**: each sampled frame has `data`, `indices`, `indptr`; `len(indptr) == H+1`; `indptr[-1] == indices.size`; `data.size == indices.size`; indices within `[0, W)` (allow empty `indices`).
- **Shape key**: `shape` is present, integer dtype, equals `[H, W]`.

# Reference snippet
```python
import json, numpy as np, cv2

VIDEO_PATH = "<path/to/video>"
INSTRUCTIONS_PATH = "<path/to/interval_instructions.json>"
MASKS_PATH = "<path/to/masks.npz>"
TARGET_FPS = 5  # from the task

ALLOWED = {"Stay", "Dolly In", "Dolly Out", "Pan Left", "Pan Right",
           "Tilt Up", "Tilt Down", "Roll Left", "Roll Right"}

cap = cv2.VideoCapture(VIDEO_PATH)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
src_fps = cap.get(cv2.CAP_PROP_FPS)
H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
cap.release()
step = max(1, int(round(src_fps / TARGET_FPS)))
n_samples = len(range(0, total, step))

# --- JSON ---
j = json.load(open(INSTRUCTIONS_PATH))
assert isinstance(j, dict) and len(j) > 0
keys = sorted(j.keys(), key=lambda k: int(k.split("->")[0]))
cursor = 0
for k in keys:
    s, e = k.split("->")
    assert s.isdigit() and e.isdigit(), k
    s, e = int(s), int(e)
    assert s == cursor, f"gap/overlap at {k}, expected start {cursor}"
    assert s < e <= n_samples, (k, n_samples)
    lbls = j[k]
    assert isinstance(lbls, list) and lbls, k
    for lbl in lbls:
        assert isinstance(lbl, str) and lbl in ALLOWED, lbl
    cursor = e
assert cursor == n_samples, (cursor, n_samples)

# --- NPZ ---
npz = np.load(MASKS_PATH)
assert "shape" in npz.files
sh = npz["shape"]
assert int(sh[0]) == H and int(sh[1]) == W, (sh, H, W)
frames = 0
while f"f_{frames}_data" in npz.files:
    frames += 1
assert frames == n_samples, (frames, n_samples)
# ensure no stray extras
assert f"f_{frames}_data" not in npz.files
for k in range(frames):
    d = npz[f"f_{k}_data"]
    idx = npz[f"f_{k}_indices"]
    ip = npz[f"f_{k}_indptr"]
    assert ip.shape[0] == H + 1
    assert int(ip[-1]) == idx.size
    assert d.size == idx.size
    if idx.size > 0:
        assert 0 <= int(idx.min()) and int(idx.max()) < W
```

# Mask fill sanity window (format-agnostic plausibility check)
Format checks only catch *structural* errors; they can't tell you a detector was too conservative or too permissive. If the task implies moving objects exist but your masks are mostly empty, downstream mask-IoU style metrics collapse to zero. And if the masks are mostly parallax leakage, IoU also collapses. After the structural checks above, compute a rough fill summary and only ship if it lands in a plausible window:

```python
fills = []
for k in range(frames):
    ip = npz[f"f_{k}_indptr"]
    fills.append(int(ip[-1]) / float(H * W))
mean_fill = sum(fills) / len(fills)
empty_frac = sum(1 for f in fills if f == 0) / len(fills)
max_fill = max(fills) if fills else 0.0
print(f"mean_fill={mean_fill:.4%}  empty_frac={empty_frac:.2%}  max_fill={max_fill:.4%}")

# Heuristics (ceiling depends on the egomotion label mix):
# - mean_fill < ~0.1% or empty_frac > ~0.5 ⇒ too conservative; relax threshold / min_area.
# - In a pan/tilt-only clip (no Dolly label anywhere): mean_fill > ~6–8% or any single
#   frame > ~10% ⇒ parallax leakage. Escalate the mask skill's precision ladder.
# - In a clip with any Dolly label: tighten the ceiling to mean_fill ≲ ~2–3% and any
#   single frame ≲ ~5%. The 4–8% "medium-fill" band that looks plausible under a pure
#   pan is near-field clutter under a dolly-forward walking shot and costs IoU heavily.
#   If the mean_fill is in that band *and* you cannot name the moving object in each
#   high-fill frame's overlay, retighten the mask skill (border suppression, biquadratic
#   flow, higher K, temporal persistence gate, intersection fusion, component shape gate)
#   rather than shipping as-is.
# - A frame mask that is empty is better than a frame mask of leaked parallax when no
#   visually-identifiable moving object is present — IoU on an empty mask is 0 at worst
#   whereas a false-positive mask actively lowers the IoU denominator.
```

This is a loud warning, not a hard assert — some scenes genuinely have very little motion, and some genuinely have a large moving object (close-up vehicle, crowd). But in combination with motion labels like `Pan*`/`Tilt*`/`Dolly*` from the egomotion step, a near-zero mean fill *or* a double-digit mean fill is a strong signal that the mask thresholds need to be revisited before shipping. **Under a Dolly label a "midrange" mean fill in the 4–8% band is itself suspicious** — it is almost never 1–3 pedestrian-sized objects per frame; it is almost always leaked near-field parallax, and the mask skill's precision ladder should be re-walked before shipping.

# Self-check list
- [ ] JSON keys parse as integers; every `start < end`.
- [ ] Keys partition `[0, n_samples)` with no gap and no overlap.
- [ ] Every label value is in the allowed set; list is non-empty.
- [ ] NPZ `shape == [H, W]`; `n_samples` frames present; CSR triples consistent for each; indices within `[0, W)`.
- [ ] No extra `f_{k}_*` keys beyond `n_samples`.
- [ ] Mask fill sanity window reviewed, with the ceiling chosen by the egomotion label mix (≲ 2–3% mean under a Dolly label; ≲ 4% mean for pan/tilt-only clips). No single frame ships above its ceiling (~5% dolly / ~10% pan/tilt) without a named, visually-identifiable moving object. Near-empty *or* over-ceiling masks trigger a threshold revisit, not a submission.
