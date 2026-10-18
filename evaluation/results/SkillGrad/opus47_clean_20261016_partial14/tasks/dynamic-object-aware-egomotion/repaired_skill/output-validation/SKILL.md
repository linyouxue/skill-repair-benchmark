---
name: output-validation
description: "Local self-check of instructions and mask outputs (format/range/consistency, numeric + convention + scene-grounded gates) without using GT, with proof-of-execution artifacts."
---

# When to use
- After generating your outputs (interval instructions, masks, etc.), before submission/hand-off.

# Format / structural checks
- **Key format**: every key is `"{start}->{end}"`, integers only, `start<=end`.
- **Coverage**: max frame index ≤ video total-1; consistent with your sampling policy.
- **Sample-count invariant**: `len(sample_ids) == 1 + (n - 1) // stride` (equivalently `len(sample_ids) == len(range(0, n, stride))`). Any deviation from the plain-stride set is a grader-alignment hazard — see `sampling-and-indexing` Pseudocode.
- **Frame count**: NPZ `f_{i}_*` count equals sampled frame count; no gaps or missing components.
- **CSR integrity**: each frame has `data/indices/indptr`; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices within `[0,W)`.
- **Value validity**: JSON values are non-empty string lists; labels in the allowed set.
- **Pair→frame alignment**: key count matches the convention chosen in `sampling-and-indexing` (interval-keyed → `N-1` pre-compression; per-frame → `N`). Mismatch indicates silent mode mixing.

# Reference snippet
```python
import json, numpy as np, cv2
cap=cv2.VideoCapture(VIDEO_PATH)
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); H=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); W=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
j=json.load(open(INSTRUCTIONS_PATH))
npz=np.load(MASKS_PATH)
# Sample-count invariant — catches `append(n-1)` or any post-hoc insertion.
assert len(sample_ids) == 1 + (n - 1) // stride, (
    f"len(sample_ids)={len(sample_ids)} != len(range(0,{n},{stride}))="
    f"{1 + (n - 1) // stride}; see sampling-and-indexing")
for k,v in j.items():
    s,e=k.split("->"); assert s.isdigit() and e.isdigit()
    s=int(s); e=int(e); assert 0<=s<=e<n
    for lbl in v: assert isinstance(lbl,str)
```

# Three semantic gates — in order, each is a shipping-blocker

Format validity is necessary but not sufficient. **Every gate below must
produce a trace line that cannot be forged by self-consistent code** —
observed values from real artifacts, actual file paths on disk, prose
descriptions of real scene content. A gate the producing pipeline can
satisfy without external grounding is self-consistent, not a check.

## Gate 1 — Numeric red flags on the written distribution

```python
masks = [decode_csr(npz, i, H, W) for i in range(n_sampled)]
empty_frac = sum(not m.any() for m in masks) / len(masks)
max_cov    = max(m.mean() for m in masks) if masks else 0.0
pair_labels = flatten_intervals_to_per_pair(j, n_sampled)  # list[set[str]]
frac_non_stay = sum(ls != {"Stay"} for ls in pair_labels) / max(1, len(pair_labels))
dominant_dir_frac = max(
    sum(d in ls for ls in pair_labels) / max(1, len(pair_labels))
    for d in ("Pan Left","Pan Right","Tilt Up","Tilt Down","Dolly In","Dolly Out")
)
```

| Trigger                                              | Diagnosis                             | Where to retune                                          |
|------------------------------------------------------|---------------------------------------|----------------------------------------------------------|
| `len(sample_ids) != 1 + (n-1)//stride`                | sampling off-by-one from `append(n-1)` | `sampling-and-indexing` Pseudocode (strip the append)    |
| `empty_frac > 0.20`                                   | mask filters over-pruning             | `dyn-object-masks` False-negative guardrails             |
| `max_cov < 0.01`                                      | mask threshold too high               | lower `K_MAD`, loosen persistence                        |
| `max_cov > 0.50`                                      | façade slipped through                | tighten `MAX_ASPECT`                                     |
| `max_cov > 0.30` AND filters were loosened            | loosening-driven inflation            | retighten most recent loosening (see parallax-robust-masks) |
| `has_x_stay_x_sandwich(pair_labels)`                  | smoothing window too wide             | `egomotion-estimation` Temporal smoothing                |
| dominant label == `Stay` on motion-prior scene         | MAD-saturated calibration             | `egomotion-estimation` Adaptive thresholding (saturation fallback) |
| `frac_non_stay > 0.90`                                | fallback over-triggered → threshold too low | `egomotion-estimation` Adaptive thresholding (prefer physical floor over `0.25×median`) |
| `dominant_dir_frac > 0.60` with variable-motion prior | polarity likely inverted              | re-run external anchor; see `egomotion-estimation` sign-convention external anchor |
| dominant label on `forbid_dominant` list              | thresholds mis-calibrated             | `egomotion-estimation` Adaptive thresholding             |

Do NOT tune the pipeline to clear a Gate 1 red flag; the red flags fire
back to the section that produced the distribution, where the root
cause (sign polarity, threshold calibration, filter stacking) lives.

## Gate 2 — Convention gate (sign + alignment)

Direction labels and pair-to-frame alignment both have multiple viable
conventions. A silent sign flip inverts every label; the self-test alone
cannot catch an inverted pinned table because the test's classifier and
its assertion both read the table. Gate 2 requires **two independent
lines in the trace**:

- **External-anchor trace line** (correctness anchor on a real pair):
  the first sampled pair was loaded, 2–3 features tracked, observed
  displacement logged, and a prose description of the camera's actual
  motion recorded alongside the classifier's emitted label on that
  pair. See `egomotion-estimation` "Sign-convention external anchor".
  Verification: grep the trace for `external-anchor:pass` AND a prose
  line containing camera-motion vocabulary (`panning`, `tilting`,
  `dollying`, `shifting`, `expanding`, `contracting`). A pass token
  without a prose line counts as "not run".
- **4-case self-consistency tokens** (self-consistency on classifier
  internals): four synthetic cases must have passed through the exact
  pipeline. Verification: grep for all four tokens — `sign-test:
  pan-left:pass`, `sign-test:pan-right:pass`, `sign-test:tilt-up:pass`,
  `sign-test:dolly-in:pass`. A single-token "self-test passed" line is
  insufficient (hides a partial self-test).
- **Pair→frame alignment**: the chosen convention (interval-keyed /
  start-frame / end-frame / midpoint) must be logged in-trace, and the
  emitted key count must match it.

```python
# Minimal convention gate — external anchor FIRST (correctness), then self-consistency.
assert "external-anchor:pass" in run_trace, (
    "external anchor not pass; sign convention not correctness-checked, "
    "do not ship — see egomotion-estimation sign-convention external anchor")
assert any(kw in run_trace for kw in (
    "panning", "tilting", "dollying", "shifting", "expanding", "contracting")), (
    "no prose description of camera motion found; `external-anchor:pass` "
    "without prose counts as not-run — re-run the external anchor")
for token in ("sign-test:pan-left:pass",
              "sign-test:pan-right:pass",
              "sign-test:tilt-up:pass",
              "sign-test:dolly-in:pass"):
    assert token in run_trace, (
        f"missing {token}; 4-case self-consistency incomplete")
assert "pair-alignment:" in run_trace, (
    "pair→frame alignment convention not logged; log and re-verify key count")
```

Corrective action on failure: external-anchor miss → run
`egomotion-estimation` "Sign-convention external anchor" on
`frames[sample_ids[0]]`, `frames[sample_ids[1]]`; log prose; re-run
classifier. 4-case miss → run `references/sign-convention-selftest.md`
end-to-end. Prose keyword miss → re-write the anchor step to log the
camera motion in English (not just a numeric dx/dy).

## Gate 3 — Scene-grounded gate (mask overlays with proof-of-execution)

Gate 1 is tunable from inside the producing pipeline (loosening to clear
the band). Gate 3 requires **artifacts on disk** that cannot be forged
by writing a verdict string into the trace:

1. **Overlay PNG file(s) written to disk** at a path logged in-trace.
2. **Prose description per verdict** naming what the blob covers in
   English scene-content vocabulary (e.g. "bottom-left blob overlaps
   visible pedestrian wearing red jacket" / "upper-right blob covers
   static building façade"), not just the enum tag.
3. **Verdict enum** per inspected frame: `dynamic` / `false_positive` /
   `ambiguous`.

```python
verdicts = inspect_mask_overlays(masks, sampled_frames, sample_ids, k_frames=3)
for v in verdicts:
    # Proof-of-execution: PNG file must exist on disk.
    assert os.path.exists(v["overlay_path"]), (
        f"overlay PNG missing at {v['overlay_path']} — Gate 3 not run")
    # Prose description cannot be a bare enum tag.
    assert v.get("prose") and any(
        kw in v["prose"].lower()
        for kw in ("pedestrian","vehicle","car","person","cyclist","animal",
                   "façade","facade","building","wall","sky","foliage","road",
                   "parked","static")), (
        f"verdict for frame {v['sample_id']} has no scene-content prose; "
        f"a bare enum tag counts as not-run — re-open the overlay and describe")
    assert v["verdict"] in ("dynamic","false_positive","ambiguous"), v
# Any false_positive verdict → retighten the most recent loosening,
# NOT loosen further; see dyn-object-masks "Scene-grounded exit".
assert all(v["verdict"] == "dynamic" for v in verdicts), verdicts
```

Gate 3 is required **unconditionally** — not only after loosening. A
first-try pass through the numeric band is still self-consistent until
anchored to real scene content.

Read `references/semantic-sanity-check.md` for the full branched retry
procedure across all three gates, including the scene-prior table and
the branch-by-branch corrective actions. Skip when outputs are purely
format-only graded and no retry budget remains.

# Self-check list
- [ ] JSON keys/values pass format checks; key count matches the pair→frame alignment convention logged by `sampling-and-indexing`.
- [ ] **Sample-count invariant checked:** `len(sample_ids) == 1 + (n-1)//stride`; `sample_ids` is exactly `list(range(0, n, stride))` with no post-hoc insertion.
- [ ] Max frame index within video range and near sampled max.
- [ ] NPZ frame count matches sampling; CSR `shape` validated.
- [ ] **Gate 1 (numeric):** `empty_frac ≤ 0.20`, `0.01 ≤ max_cov ≤ 0.50`, no `X / Stay / X` sandwich, dominant label consistent with scene prior, `frac_non_stay ≤ 0.90`, no non-Stay direction dominates > 60% on a variable-motion scene.
- [ ] **Gate 2 (convention):** `external-anchor:pass` in-trace AND a prose line with camera-motion vocabulary; all four self-consistency pass tokens present; pair→frame alignment convention logged.
- [ ] **Gate 3 (scene-grounded):** 2–3 overlay PNG files exist on disk at logged paths; each verdict carries a prose scene-content description; all verdicts are `dynamic`; `max_cov > 0.30` after loosening triggers retighten, not another loosening pass.

# Common pitfalls
- **Ticked-but-not-executed gates.** The self-check list is being
  completed without the gate's substantive action occurring: a
  `sign-convention self-test: pass` line emitted without the four axis
  tokens; a Gate-3 verdict string written without an overlay PNG on
  disk; a prose-field left as a bare enum tag. Every gate line in-trace
  must point at an artifact that could not be produced by the pipeline
  alone — an actual file path, a four-token enumeration, a prose
  sentence naming real scene content.
- **Self-consistent gates.** Treating gates the producing pipeline can
  trivially satisfy as terminal checks: format counts matching sampled
  counts when sampled counts are themselves wrong; sign self-tests
  whose classifier branch and assertion both read the same pinned
  table; numeric bands satisfied by loosening the filters that
  measured them. Pair any self-tunable gate with an external anchor
  (real-pair observation, PNG on disk, task-spec reference pair).
- **Loosening to clear a numeric gate the executor itself owns.** The
  numeric band (`empty_frac`, `max_cov`, `frac_non_stay`) is tunable
  from the mask filter stack and the threshold calibration — a
  dominant-label or over-triggered-fallback distribution can pass the
  gate by driving the band to a different wrong place. Red flags fire
  back to the producing section; do NOT tune to clear them.
- **Selection-bias in self-testing.** Self-testing only the pipeline
  nodes that *feel* risky (sign, parallax, filter tuning) and skipping
  primitive invariants (sample count, index range, trailing-frame
  alignment, dominant-direction fraction) the skill itself may silently
  violate. Run every gate, including the ones that look trivial.
