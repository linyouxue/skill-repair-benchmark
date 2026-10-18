# Semantic sanity check — three gates + branched retry

Trigger: `output-validation`'s L2 pointer fires when any gate has a red
flag (numeric red flag, convention check missing, scene-grounded verdict
negative), OR when source frames are accessible and you want a precommit
audit across all three gates.

Structure: Gate 1 (numeric audit) → Gate 2 (convention: external anchor +
self-consistency) → Gate 3 (scene-grounded verdict with PNG + prose) →
branch to the right re-tune → re-run the producing pipeline → re-audit.
Gates 2 and 3 exist because Gate 1 is tunable from inside the producing
pipeline. Gate 2's external-anchor layer exists because its
self-consistency layer alone is tautological.

## Pass 1 — Numeric audit of written outputs

```python
import json, numpy as np, cv2
from scipy.sparse import csr_matrix

def decode_csr(npz, i, H, W):
    data   = npz[f"f_{i}_data"]
    idx    = npz[f"f_{i}_indices"]
    indptr = npz[f"f_{i}_indptr"]
    return csr_matrix((data, idx, indptr), shape=(H, W)).toarray().astype(bool)

def mask_distribution(masks_npz_path, n_sampled):
    npz = np.load(masks_npz_path)
    H, W = int(npz["shape"][0]), int(npz["shape"][1])
    masks = [decode_csr(npz, i, H, W) for i in range(n_sampled)]
    empty_frac = sum(not m.any() for m in masks) / len(masks)
    covs = [float(m.mean()) for m in masks]
    return {"empty_frac": empty_frac,
            "max_cov": max(covs) if covs else 0.0,
            "mean_cov": float(np.mean(covs)) if covs else 0.0,
            "masks": masks}

def flatten_intervals(instructions_json, n_sampled):
    j = json.load(open(instructions_json))
    per_pair = [None] * (n_sampled - 1)
    for key, labels in j.items():
        s, e = (int(x) for x in key.split("->"))
        for k in range(s, e):
            if 0 <= k < len(per_pair):
                per_pair[k] = set(labels)
    return per_pair

def find_x_stay_x(seq):
    bad = []
    for i in range(1, len(seq) - 1):
        p, c, nx = seq[i-1], seq[i], seq[i+1]
        if c == {"Stay"} and p == nx and p is not None and p != {"Stay"}:
            bad.append(i)
    return bad

def label_fractions(pair_labels):
    """Return frac_non_stay and the max single non-Stay direction fraction."""
    n = max(1, sum(1 for s in pair_labels if s is not None))
    frac_non_stay = sum(1 for s in pair_labels
                        if s is not None and s != {"Stay"}) / n
    dirs = ("Pan Left","Pan Right","Tilt Up","Tilt Down","Dolly In","Dolly Out")
    dominant_dir_frac = 0.0
    for d in dirs:
        f = sum(1 for s in pair_labels if s is not None and d in s) / n
        dominant_dir_frac = max(dominant_dir_frac, f)
    return frac_non_stay, dominant_dir_frac
```

## Verification + corrective action — branched

### Branch A — mask over-pruning (`empty_frac > 0.20` or `max_cov < 0.01`)

```python
dist = mask_distribution(masks_npz, n_sampled)
if dist["empty_frac"] > 0.20 or dist["max_cov"] < 0.01:
    # Return to dyn-object-masks and loosen filters IN THIS ORDER:
    #   1. disable persistence (or switch to warped-neighbor)
    #   2. raise MAX_AREA to 0.40*H*W
    #   3. lower K_MAD from 3.0 → 2.5
    # Re-run the mask pipeline, then re-call mask_distribution.
    raise AssertionError(
        f"over-pruned: empty_frac={dist['empty_frac']:.2f}, "
        f"max_cov={dist['max_cov']:.3f}; loosen filters per "
        f"references/parallax-robust-masks.md and re-run")
```

### Branch B — façade slipping through (`max_cov > 0.50`)

```python
if dist["max_cov"] > 0.50:
    raise AssertionError(
        f"over-permissive: max_cov={dist['max_cov']:.2f}; "
        f"tighten MAX_ASPECT and re-run")
```

### Branch C — label sandwich (`X / Stay / X`)

```python
pair_labels = flatten_intervals(instructions_json, n_sampled)
bad = find_x_stay_x(pair_labels)
if bad:
    raise AssertionError(
        f"X/Stay/X sandwich at pair indices {bad}; retune per "
        f"references/adaptive-motion-thresholds.md and re-run")
```

### Branch D — scene prior / dominant-fraction violated

```python
SCENE_PRIORS = {
    "walking_pov":  {"expected_dominant": "Dolly In",
                     "forbid_dominant":   {"Stay"}},
    "tripod":       {"expected_dominant": "Stay",
                     "forbid_dominant":   {"Dolly In", "Dolly Out"}},
    "dashcam":      {"expected_dominant": "Dolly In",
                     "forbid_dominant":   {"Stay"}},
}

def label_dominant(pair_labels):
    flat = [l for s in pair_labels if s for l in s]
    return max(set(flat), key=flat.count) if flat else None

prior = SCENE_PRIORS.get(scene_type)
frac_non_stay, dominant_dir_frac = label_fractions(pair_labels)

if prior and label_dominant(pair_labels) in prior["forbid_dominant"]:
    # Thresholds mis-calibrated (dominant Stay on motion scene → MAD
    # saturated high; see references/adaptive-motion-thresholds.md Mode 1).
    raise AssertionError(
        f"prior violated: dominant={label_dominant(pair_labels)} "
        f"forbidden for scene={scene_type}; retune calibration")

if frac_non_stay > 0.90:
    # Fallback over-triggered (threshold too low). See Mode 2 — prefer
    # a physical floor over 0.25*median.
    raise AssertionError(
        f"frac_non_stay={frac_non_stay:.2f} > 0.90; MAD-saturation "
        f"fallback likely over-triggered. Switch to physical floor "
        f"max(TRANS_FLOOR_PX, stride/8) in adaptive thresholding; do "
        f"NOT tune to clear this red flag.")

if dominant_dir_frac > 0.60:
    # Polarity likely inverted on the dominant axis — NOT a threshold
    # problem. Re-run Branch F (external anchor on a different pair).
    raise AssertionError(
        f"dominant_dir_frac={dominant_dir_frac:.2f} > 0.60; polarity "
        f"likely inverted. Re-run external anchor (Branch F) on a "
        f"different real sampled pair; do NOT retune thresholds.")
```

### Branch E — loosening-driven inflation (`max_cov > 0.30` after loosening)

```python
loosen_log = read_mask_loosen_log()
if loosen_log and dist["max_cov"] > 0.30:
    raise AssertionError(
        f"loosening-driven inflation: max_cov={dist['max_cov']:.3f} "
        f"with loosen_log={loosen_log}; retighten the most recent step "
        f"(see parallax-robust-masks.md) and re-run")
```

### Branch F — sign/alignment convention not demonstrated

```python
# Direction labels and pair→frame alignment are decision points that flip
# every label or shift every interval if silently wrong. Both must be
# demonstrated this run — and the sign convention requires BOTH layers:
# external anchor on a real pair (correctness) AND self-consistency.
run_trace = read_run_trace()

# Layer A — correctness anchor on a real sampled pair
if "external-anchor:pass" not in run_trace:
    raise AssertionError(
        "external-anchor:pass missing — sign convention has only been "
        "self-consistency-tested (which is tautological). Run Layer A "
        "of references/sign-convention-selftest.md on frames[sample_ids[0]], "
        "frames[sample_ids[1]] before shipping.")

# Prose line check — a pass token without a prose line counts as not-run.
if not any(kw in run_trace for kw in (
        "panning", "tilting", "dollying", "shifting",
        "expanding", "contracting")):
    raise AssertionError(
        "external-anchor:pass present but no prose camera-motion "
        "description found; a pass token without prose counts as "
        "not-run — re-run the external anchor and log the prose.")

# Layer B — self-consistency on four axes
for token in ("sign-test:pan-left:pass", "sign-test:pan-right:pass",
              "sign-test:tilt-up:pass",  "sign-test:dolly-in:pass"):
    if token not in run_trace:
        raise AssertionError(
            f"missing {token}; 4-case self-consistency incomplete — "
            f"see references/sign-convention-selftest.md Layer B")

if "pair-alignment:" not in run_trace:
    raise AssertionError(
        "pair→frame alignment convention not logged — "
        "see sampling-and-indexing 'Pair-to-frame label alignment'")
```

## Pass 2 — Overlay audit + per-frame verdict (primary for mask semantics)

Even after Pass 1 passes, overlay 2–3 non-empty mask frames and record a
verdict per frame — with a PNG on disk, a prose scene-content line, and
an enum tag. See `references/parallax-robust-masks.md` → "Scene-grounded
exit" for the `inspect_mask_overlays` helper and the vocabulary rubric.

```python
verdicts = inspect_mask_overlays(dist["masks"], frames_bgr, sample_ids,
                                 k_frames=3, out_dir="overlays")
# Executor opens each PNG and fills prose + verdict.

# Proof-of-execution checks — a dict with no on-disk PNG, or with no
# prose, counts as "not run" and blocks shipping.
for v in verdicts:
    if not (v.get("overlay_path") and os.path.exists(v["overlay_path"])):
        raise AssertionError(f"overlay PNG missing for {v}; Gate 3 not run")
    if not v.get("prose"):
        raise AssertionError(f"prose missing for {v}; re-open the PNG")
    if v["verdict"] in ("false_positive", "ambiguous"):
        # Retighten (NOT loosen) and re-run; see Branch E / parallax-robust-masks.
        raise AssertionError(f"scene-grounded verdict failed: {verdicts}")
```

Verification: if all verdicts are `dynamic` with PNGs on disk and prose
lines AND Branches A–F all pass, ship. If any branch raised, fix per
that branch's corrective action and re-audit all gates from the top
(gate ordering matters — a fix to Branch F may invalidate Pass 1
numbers; a Branch D polarity fix may require re-running Branch F).
