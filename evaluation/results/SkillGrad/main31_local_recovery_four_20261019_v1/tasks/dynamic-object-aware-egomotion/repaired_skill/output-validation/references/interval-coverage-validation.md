# Interval coverage validation (inclusive endpoints)

Use this when you compress per-index values (per sampled frame or per video frame) into `"start->end"` interval keys and need to guarantee the consumer interprets endpoints as **valid indices**.

## Procedure

### 1) Parse keys and determine bounds
Decide whether keys are on the **sampled-index** axis (`0..sample_count-1`) or the **video-frame** axis (`0..total_frames-1`).

```python
def parse_interval_key(k: str) -> tuple[int, int]:
    s, e = k.split("->")
    if not (s.isdigit() and e.isdigit()):
        raise ValueError(f"Non-integer interval key: {k}")
    return int(s), int(e)

index_domain = "sampled"  # or "video"
max_valid = (sample_count - 1) if index_domain == "sampled" else (total_frames - 1)
```

### 2) Branch: validate bounds + order
Runtime branch: fail fast on out-of-range or reversed intervals.

```python
intervals = [parse_interval_key(k) for k in interval_dict.keys()]
for s, e in intervals:
    if not (0 <= s <= e <= max_valid):
        raise ValueError(f"Interval {s}->{e} out of bounds for max_valid={max_valid}")
```

### 3) Branch: validate exact coverage (no gaps, no overlaps)
Interpret intervals as inclusive and expand to indices. For large ranges, you can validate via counts rather than full expansion; expansion is simplest and often fast enough for sampled indices.

```python
from collections import Counter

covered = []
for s, e in sorted(intervals):
    covered.extend(range(s, e + 1))

counts = Counter(covered)
missing = [i for i in range(0, max_valid + 1) if counts[i] == 0]
overlap = [i for i, c in counts.items() if c > 1]

if missing:
    raise ValueError(f"Missing indices (gap): {missing[:10]} ...")
if overlap:
    raise ValueError(f"Overlapped indices: {overlap[:10]} ...")
```

### 4) Verification + corrective action
Verification: if any check fails, identify whether the bug is (a) **half-open compression**, (b) **wrong index domain**, or (c) **unsorted/incorrect merge logic**.

Corrective actions on failure:
- If an endpoint equals `max_valid + 1`, your compressor likely used half-open ranges (`end = next_start`). Fix compression to emit `end_inclusive = next_start - 1`, and ensure the final interval ends at `max_valid`.
- If many endpoints exceed `max_valid` by a large margin, you may be validating sampled-index keys against video-frame bounds or vice versa. Recompute `max_valid` from the correct domain.
- If you see overlaps/gaps, sort by `start`, then rebuild intervals from the original per-index sequence rather than trying to merge already-merged intervals.

### 5) Optional: rebuild intervals from per-index sequence (safe fallback)
When merge logic is suspect, recompute intervals directly from the per-index values.

```python
def compress_inclusive(values):
    out = []
    start = 0
    for i in range(1, len(values)):
        if values[i] != values[i-1]:
            out.append((start, i - 1, values[i-1]))
            start = i
    out.append((start, len(values) - 1, values[-1]))
    return {f"{s}->{e}": v for s, e, v in out}

# Verification: rerun steps 1-3 on the rebuilt dict before writing output
