# Parallax-robust dynamic-object masks — flow residual + stride-aware filters

Trigger: dyn-object-masks' scene-router pointer fires when the camera is
translation-dominated **and** per-pair RANSAC-inlier residual spread is
high (handheld walking POV, dashcam, drive-by). Affine warped-diff lights
up static near-field objects as "dynamic" in these scenes.

## Pipeline

```python
import cv2, numpy as np

def ego_flow_from_affine(M, H, W):
    """Flow field predicted by the estimated 2D affine ego-motion."""
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    xw = M[0, 0] * xs + M[0, 1] * ys + M[0, 2]
    yw = M[1, 0] * xs + M[1, 1] * ys + M[1, 2]
    return np.stack([xw - xs, yw - ys], axis=-1)   # (H, W, 2)

def parallax_robust_mask(prev_gray, curr_gray, M,
                         min_area, max_area, max_aspect,
                         k_mad=3.0):
    H, W = curr_gray.shape
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    flow = dis.calc(prev_gray, curr_gray, None)             # (H, W, 2)
    pred = ego_flow_from_affine(M, H, W)
    resid = np.linalg.norm(flow - pred, axis=-1)            # (H, W)

    med = np.median(resid)
    mad = 1.4826 * np.median(np.abs(resid - med))
    thr = med + k_mad * mad
    raw = resid > thr

    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    m = cv2.morphologyEx(raw.astype(np.uint8) * 255, cv2.MORPH_OPEN,  k3)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k7)

    n, cc, stats, _ = cv2.connectedComponentsWithStats(m > 0, connectivity=8)
    out = np.zeros((H, W), dtype=bool)
    for cid in range(1, n):
        area = stats[cid, cv2.CC_STAT_AREA]
        w    = stats[cid, cv2.CC_STAT_WIDTH]
        h    = stats[cid, cv2.CC_STAT_HEIGHT]
        aspect = max(w, h) / max(1, min(w, h))
        if min_area <= area <= max_area and aspect <= max_aspect:
            out |= (cc == cid)
    return out, resid, flow
```

## Branch — Flow backend selection

- `cv2.DISOpticalFlow_create` is available in OpenCV ≥ 4.x. If import fails
  or runtime is too slow for the sampled count, fall back:
  ```python
  flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None,
                                      0.5, 3, 15, 3, 5, 1.2, 0)
  ```
- Both return `(H, W, 2)` with the same convention; the rest of the
  pipeline is unchanged.

## Parameter starting points (generous — biased against over-pruning)

```python
K_MAD           = 3.0                    # NOT 4; 4 compounds with later filters
MIN_AREA        = int(5e-4 * H * W)      # ~380 px on 1080p
MAX_AREA        = int(0.25 * H * W)      # 25% of frame; close-up cars/people need this room
MAX_ASPECT      = 6.0
STRIDE_PERSIST_DISABLE = 8               # drop raw-mask persistence at/above this stride
```

Why `MAX_AREA = 0.25 * H*W` and not `0.08`: an 8% cap discards a close-up
vehicle or pedestrian that legitimately occupies ~15–30% of a 720×1280
frame. Facade/foreground-slab rejection is the aspect-ratio + compactness
filter's job, not the area cap's.

## Temporal persistence — stride-aware

A true pedestrian/vehicle appears across ≥2 consecutive sampled frames,
**but at large stride the object moves off its own previous footprint**.
Raw-mask overlap is only valid at small stride. Choose a branch by stride:

```python
def enforce_persistence(masks, flows, stride, min_overlap_frac=0.1,
                        stride_persist_disable=8):
    # Branch A — stride large: disable persistence entirely, trust area/aspect.
    if stride >= stride_persist_disable and flows is None:
        return [m.copy() for m in masks]

    # Branch B — flows available: warp each neighbor mask into current frame
    # before computing overlap.
    out = [np.zeros_like(m) for m in masks]
    H, W = masks[0].shape
    for i, mi in enumerate(masks):
        n, cc, stats, _ = cv2.connectedComponentsWithStats(mi.astype(np.uint8), 8)
        for cid in range(1, n):
            comp = (cc == cid)
            comp_area = comp.sum()
            keep = False
            for j in (i - 1, i + 1):
                if not (0 <= j < len(masks)):
                    continue
                if flows is not None:
                    neighbor = warp_mask_with_flow(masks[j], flows, src=j, dst=i)
                else:
                    # Branch C — no flow available: dilate neighbor by expected displacement
                    expected_disp_px = max(10, 2 * stride)
                    kernel = cv2.getStructuringElement(
                        cv2.MORPH_ELLIPSE,
                        (2 * expected_disp_px + 1, 2 * expected_disp_px + 1))
                    neighbor = cv2.dilate(masks[j].astype(np.uint8), kernel).astype(bool)
                overlap = np.logical_and(comp, neighbor).sum()
                if overlap >= min_overlap_frac * comp_area:
                    keep = True; break
            if keep:
                out[i] |= comp
    return out
```

## Scene-grounded exit — overlay PNG + prose verdict + enum

The numeric emptiness band (`empty_frac ≤ 0.20`, `max_cov ∈ [0.01, 0.50]`)
is tunable from inside the retry loop. On a parallactic scene, a static
near-field façade can produce a residual blob that passes the band after
loosening — the band alone cannot distinguish it from a real moving
object. Before shipping, the gate requires three independent artifacts
per inspected frame:

1. **Overlay PNG file on disk** at a path logged in-trace (proof of
   execution — a verdict dict written in memory with no PNG counts as
   not-run).
2. **Prose line** naming what the largest blob covers in English
   scene-content vocabulary (`pedestrian`, `vehicle`, `cyclist`,
   `façade`, `building`, `sky`, `foliage`, `parked`, etc.). A bare enum
   tag counts as not-run.
3. **Verdict enum** in `{dynamic, false_positive, ambiguous}`.

```python
import os, cv2, numpy as np

def _overlay(frame_bgr, mask_bool, alpha=0.5):
    out = frame_bgr.copy()
    red = np.zeros_like(out); red[..., 2] = 255
    out[mask_bool] = (alpha * red[mask_bool] +
                      (1 - alpha) * out[mask_bool]).astype(np.uint8)
    return out

def inspect_mask_overlays(masks, sampled_frames_bgr, sample_ids,
                          k_frames=3, out_dir="overlays"):
    """Save overlays for the max-cov, first-non-empty, and one random
    non-empty mask frame. Returns a list of verdict dicts (one per
    inspected frame). The executor must open each PNG and fill
    verdict['prose'] + verdict['verdict'] by looking at the image."""
    os.makedirs(out_dir, exist_ok=True)
    non_empty = [i for i, m in enumerate(masks) if m.any()]
    if not non_empty:
        return [{"idx": None, "verdict": "all_empty",
                 "overlay_path": None, "prose": "no non-empty masks"}]

    covs = [(i, float(masks[i].mean())) for i in non_empty]
    max_cov_i = max(covs, key=lambda t: t[1])[0]
    first_i   = non_empty[0]
    rand_i    = non_empty[len(non_empty) // 2]
    picks = sorted(set([max_cov_i, first_i, rand_i]))[:k_frames]

    verdicts = []
    for i in picks:
        png = os.path.join(out_dir, f"overlay_{sample_ids[i]}.png")
        cv2.imwrite(png, _overlay(sampled_frames_bgr[i], masks[i]))
        # Verify the PNG actually hit disk (proof-of-execution).
        assert os.path.exists(png) and os.path.getsize(png) > 0, (
            f"overlay PNG missing or empty at {png}")
        print(f"overlay-written: sample_id={sample_ids[i]} path={png}")

        n, cc, stats, cents = cv2.connectedComponentsWithStats(
            masks[i].astype(np.uint8), 8)
        blobs = []
        H, W = masks[i].shape
        for cid in range(1, n):
            area = stats[cid, cv2.CC_STAT_AREA]
            cx, cy = cents[cid]
            w, h = stats[cid, cv2.CC_STAT_WIDTH], stats[cid, cv2.CC_STAT_HEIGHT]
            aspect = max(w, h) / max(1, min(w, h))
            blobs.append(dict(cid=cid, area=int(area),
                              frac=area / (H * W),
                              center=(float(cx), float(cy)),
                              aspect=float(aspect)))
        verdicts.append(dict(idx=i, sample_id=int(sample_ids[i]),
                             overlay_path=png, blobs=blobs,
                             prose=None, verdict=None))  # executor fills these
    return verdicts
```

### Per-frame verdict rubric

Open each overlay PNG; identify the largest blob (center + area in
`blobs[]`); write the prose + enum back into the verdict dict. Prose
must include at least one scene-content word from the English
vocabulary table below.

| Verdict          | Observable in overlay                                       | Prose vocabulary (choose at least one)                       | Next action                               |
|------------------|-------------------------------------------------------------|--------------------------------------------------------------|-------------------------------------------|
| `dynamic`        | blob covers a moving object                                 | pedestrian / vehicle / car / person / cyclist / animal       | continue                                  |
| `false_positive` | blob covers a static scene region                            | façade / facade / building / wall / sky / foliage / road / parked / static | retighten (see below); do NOT loosen more |
| `ambiguous`      | blob covers a boundary / mixed region                       | boundary / shadow / partial / edge                           | retighten by one step, re-run             |

Example prose: `"overlay_14.png: bottom-left blob overlaps a visible
pedestrian walking across road"` → verdict `dynamic`. Or:
`"overlay_14.png: upper-right blob covers a static building façade,
no motion"` → verdict `false_positive`.

Minimum pass bar: at least `k_frames - 1` verdicts are `dynamic`; none
is `false_positive`; every verdict has a corresponding PNG on disk and
a non-empty prose line.

```python
# Proof-of-execution assertions — the gate itself.
for v in verdicts:
    assert v.get("overlay_path") and os.path.exists(v["overlay_path"]), (
        f"verdict for frame {v.get('sample_id')} has no on-disk PNG")
    assert v.get("prose"), (
        f"verdict for frame {v['sample_id']} has no prose; re-open the PNG")
    text = v["prose"].lower()
    assert any(kw in text for kw in (
        "pedestrian","vehicle","car","person","cyclist","animal",
        "façade","facade","building","wall","sky","foliage","road",
        "parked","static","boundary","shadow","partial","edge")), (
        f"prose '{v['prose']}' lacks scene-content vocabulary; a bare enum "
        f"or numeric-only description counts as not-run")
    assert v["verdict"] in ("dynamic","false_positive","ambiguous"), v
```

## Ordered retighten branch — undo the last loosening step

The verdict is the exit condition, not the band. If any verdict is
`false_positive` (or `ambiguous`), or if `max_cov > 0.30` emerged only
after loosening, do NOT loosen further. Undo the most recently loosened
parameter, one step at a time, re-running after each step:

```python
# Loosen order (worst-to-best for over-pruning): persistence → MAX_AREA → K_MAD
# Retighten order (reverse): K_MAD → MAX_AREA → persistence
RETIGHTEN_STEPS = [
    ("K_MAD",    lambda s: s.update(K_MAD=min(3.0, s["K_MAD"] + 0.5))),
    ("MAX_AREA", lambda s: s.update(MAX_AREA_FRAC=max(0.25,
                                      s["MAX_AREA_FRAC"] - 0.075))),
    ("persist",  lambda s: s.update(persistence_disabled=False)),
]

def retighten_once(state):
    """Undo the most recently loosened parameter; return name or None."""
    for name, step in RETIGHTEN_STEPS:
        if state["loosen_log"] and state["loosen_log"][-1] == name:
            step(state); state["loosen_log"].pop()
            return name
    return None  # nothing left to retighten → the pipeline itself is wrong
```

## Verification + corrective action

Combined numeric + scene-grounded gate:

```python
empty_frac = sum(not m.any() for m in final_masks) / len(final_masks)
max_cov    = max(m.mean() for m in final_masks) if final_masks else 0.0
verdicts   = inspect_mask_overlays(final_masks, frames_bgr, sample_ids)
# Executor opens each PNG and fills prose + verdict before continuing.
scene_ok   = all(v.get("verdict") == "dynamic" for v in verdicts)
loosened   = bool(state.get("loosen_log"))

# Branch A — classic over-pruning
if empty_frac > 0.20 or max_cov < 0.01:
    # Loosen in order: persistence → MAX_AREA → K_MAD; re-run.
    raise AssertionError(f"over-pruned (empty_frac={empty_frac:.2f}, "
                         f"max_cov={max_cov:.3f}); loosen & re-run")

# Branch B — façade slipped through at any time
if max_cov > 0.50:
    raise AssertionError(f"façade slab (max_cov={max_cov:.2f}); "
                         f"tighten MAX_ASPECT and re-run")

# Branch C — loosening-driven inflation (scene-grounded red flag)
if loosened and max_cov > 0.30:
    name = retighten_once(state)
    raise AssertionError(f"loosening-driven inflation "
                         f"(max_cov={max_cov:.3f} after loosening); "
                         f"retightened '{name}', re-run")

# Branch D — scene-grounded verdict failed
if not scene_ok:
    name = retighten_once(state)
    raise AssertionError(f"scene-grounded gate failed: {verdicts}; "
                         f"retightened '{name}', re-run")
```

If all branches clear and verdicts are all `dynamic` with on-disk PNGs
and prose lines, cross-check once more via the overlay audit in
`references/semantic-sanity-check.md` (secondary) before shipping.
