---
name: output-validation
description: "Local self-check of instructions and per-frame outputs (format/range/coverage/consistency) without using ground truth."
---

## Workflow: validate before hand-off
1) Identify the **index domain** used by each output (video-frame vs sampled-index).
2) Parse and validate keys/structures (types, ranges).
3) Validate **coverage** (no gaps/overlaps) under the domain’s bounds.
4) Validate cross-artifact consistency (e.g., instruction intervals cover the same count as NPZ frames).
5) Run a **semantic spot-check** on a small sample: verify outputs mean what the evaluator expects (not just valid files).

```python
max_valid = (sample_count - 1) if index_domain == "sampled" else (total_frames - 1)
for (s, e) in parsed_intervals:
    assert 0 <= s <= e <= max_valid
```

## Interval JSON: format + sampled-index bounds + exact coverage
- Key format: `"{start}->{end}"`, integers only, `start<=end`.
- Bounds: endpoints must be within the valid range of the output’s index domain.
- Coverage: intervals should cover every index exactly once unless a spec allows omissions.

```python
def covered_indices(intervals):
    out = []
    for s, e in intervals:
        out.extend(range(s, e + 1))  # inclusive
    return out

seen = covered_indices(parsed_intervals)
assert min(seen) == 0
assert max(seen) == max_valid
assert len(seen) == (max_valid + 1)
assert len(set(seen)) == len(seen)
```

Read references/interval-coverage-validation.md when interval keys are derived from a per-index sequence (compression/merging step).
Skip when keys are not intervals.

## NPZ / CSR mask consistency
- Frame keys: ensure `f_{i}_*` are consecutive and match the expected count.
- CSR integrity per frame: `len(indptr)==H+1`, `indptr[-1]==indices.size`, `indices in [0,W)`.

```python
frames = 0
while f"f_{frames}_data" in npz:
    frames += 1
assert frames == sample_count
indptr = npz["f_0_indptr"]; indices = npz["f_0_indices"]
assert indptr.shape[0] == H + 1 and indptr[-1] == indices.size
```

## Semantic spot-check (required when evaluation is opaque)
Do this after passing format/coverage checks and before final write-out.

- Dynamic masks: confirm they highlight coherent objects, not borders/global swaths.
- Egomotion: confirm label directions match the measured motion under your chosen warp direction.

Read references/semantic-spot-check.md when you produce masks or directionful motion labels and you cannot directly evaluate against ground truth.
Skip when the output is purely structural (e.g., just re-encoding given labels).

## Common Pitfalls
- Treating format/coverage validation as sufficient even when the evaluator checks *semantics*.
- Checking only `start<=end` but not checking that `end` is within the valid index domain (sampled vs video).
- Coverage checks that ignore overlaps (set-based) or ignore gaps (only max/min checks).
- Validating one artifact in isolation and missing cross-artifact mismatches (intervals vs NPZ frame count).
