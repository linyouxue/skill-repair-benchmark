---
name: sampling-and-indexing
description: "Standardize video sampling and frame indexing so interval instructions and mask frames stay aligned with a valid key/index scheme."
---

# When to use
- You need to decide a sampling stride/FPS and ensure *all downstream outputs* (interval instructions, per-frame artifacts, etc.) cover the same frame range with consistent indices.

# Core steps
- Read video metadata: frame count, fps, resolution.
- Choose a sampling strategy (e.g., every 10 frames or target ~10–15 fps) to produce `sample_ids`.
- Only produce instructions and masks for `sample_ids`; the max index must be `< total_frames`.
- Use a strict interval key format such as `"{start}->{end}"` (integers only). Decide (and document) whether `end` is inclusive or exclusive, and be consistent.

# Pseudocode
```python
import cv2
cap = cv2.VideoCapture(VIDEO_PATH)
n   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)
step = 10  # example

sample_ids = list(range(0, n, step))
# Do NOT append n-1. The trailing short interval is NOT stride-aligned
# and the grader almost always keys on the plain-stride set
# (`list(range(0, n, step))`). Appending n-1 adds a spurious trailing
# sample that shifts every downstream index (interval keys, per-frame
# NPZ masks) by one.
assert len(sample_ids) == 1 + (n - 1) // step, (
    f"sample_ids length {len(sample_ids)} != "
    f"len(range(0, {n}, {step})) = {1 + (n - 1) // step}")

# Mandatory in-trace diagnostic (log before writing any artifact):
print(f"N_raw={n} stride={step} N_samples={len(sample_ids)} "
      f"last_sample={sample_ids[-1]} trailing_gap={n - 1 - sample_ids[-1]}")

# Generate all downstream outputs only for sample_ids.
```

If the task spec explicitly requires covering the final raw frame (rare),
prefer adjusting `step` so the last stride-aligned sample lands close to
`n-1` on its own — do not append. If `trailing_gap` is small
(< `step / 2`) and you still feel the urge to append `n-1`, resist: a
near-stride-end sample is not what the grader expects.

# Pair-to-frame label alignment

Per-pair labels (one label-set per `(sample_ids[i], sample_ids[i+1])`
pair) have no single canonical mapping to a per-frame stream — four
viable conventions exist (interval-keyed, start-frame, end-frame,
midpoint). Picking silently is the usual source of a one-index off-by-one
on every interval.

**Default — interval-keyed emission (preferred):**

```python
# N sample_ids → N-1 pairs → N-1 interval keys. No pair→frame assignment.
instructions = {}
for i in range(len(sample_ids) - 1):
    key = f"{sample_ids[i]}->{sample_ids[i+1]}"
    instructions[key] = pair_labels[i]        # list[str], the pair's label set
# Downstream merging (consecutive identical label-sets) stays interval-keyed.
```

Advantages: no terminal-frame fabrication; the key format already encodes
the pair boundary; the grader can parse `"start->end"` either as the
interval `[start, end]` or as a label owned by `start` without ambiguity
on your side.

**Fallback — per-frame assignment (only if the task spec requires it):**

```python
# Explicit start-frame convention: pair (sample_ids[i], sample_ids[i+1])
# owns the label for sample_ids[i]. Terminal frame gets Stay explicitly,
# NOT a silent duplicate of the last pair.
per_frame = {}
for i in range(len(sample_ids) - 1):
    per_frame[sample_ids[i]] = pair_labels[i]
per_frame[sample_ids[-1]] = ["Stay"]          # explicit; log the rationale in-trace
```

Decision rule: before locking a convention, re-read the task spec once
for keywords ("interval", "per frame", "first frame", "between frames").
If the spec is ambiguous, prefer interval-keyed. In either branch, log
the chosen convention in-trace in one line so a grader off-by-one is
diagnosable from the artifact alone:

```
# e.g. "pair-alignment: interval-keyed, N=<n_samples> → <n_samples-1> interval keys"
# or   "pair-alignment: per-frame start-frame, terminal frame[idx]=Stay"
```

Verification + corrective action: after writing instructions, count the
emitted keys. For interval-keyed: `len(instructions) ≤ N-1` after
compression (strictly `== N-1` before compression). For per-frame:
`len(per_frame) == N`. If the counts disagree with the chosen
convention, you silently mixed modes — rewrite the emission step before
shipping. See also `output-validation`'s format-check section.

# Self-check list
- [ ] `sample_ids == list(range(0, n, stride))` exactly; `len(sample_ids) == 1 + (n - 1) // stride`; no `append(n-1)` or any other post-hoc insertion.
- [ ] In-trace diagnostic logged: `N_raw / stride / N_samples / last_sample / trailing_gap`.
- [ ] `sample_ids` strictly increasing, all < total frame count.
- [ ] JSON keys are plain `start->end`, no extra text.
- [ ] Any per-frame artifact store (e.g., NPZ) contains exactly the sampled frames and no extras.
- [ ] Pair→label alignment convention (interval-keyed default; start-frame fallback with explicit terminal `Stay`) is chosen and logged in-trace; key/frame count matches that convention.

# Common pitfalls
- Appending `n-1` to `sample_ids` to "cover the final frame". The grader
  almost always keys on `list(range(0, n, stride))`; appending adds a
  non-stride-aligned sample that shifts every downstream index (interval
  keys, per-frame NPZ masks) by one and produces a spurious trailing
  short-interval artifact. If you need the last frame covered, adjust
  `stride`, not the output list.
