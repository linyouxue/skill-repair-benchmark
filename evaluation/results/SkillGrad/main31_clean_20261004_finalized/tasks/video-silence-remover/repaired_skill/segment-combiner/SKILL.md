---
name: segment-combiner
description: Combine multiple segment detection results into a unified list. Use when you need to merge segments from different detectors, prepare removal lists for video processing, or consolidate detection outputs.
---

# Segment Combiner

Combines multiple segment JSON files into a single unified segments file for video processing.

## Use Cases

- Merging segments from multiple detectors
- Consolidating detection results
- Preparing unified input for video-processor

## Usage

```bash
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments /path/to/segments1.json /path/to/segments2.json \
    --output /path/to/all_segments.json
```

### Parameters

- `--segments`: One or more segment JSON files to combine
- `--output`: Path to output combined segments JSON

### Input Format

Each input file should have a `segments` array:

```json
{
  "segments": [
    {"start": 0, "end": 120, "duration": 120},
    {"start": 300, "end": 305, "duration": 5}
  ]
}
```

### Output Format

```json
{
  "segments": [
    {"start": 0, "end": 120, "duration": 120},
    {"start": 300, "end": 305, "duration": 5}
  ],
  "total_segments": 2,
  "total_duration_seconds": 125
}
```

## Reconcile detector outputs before final removal

When two detectors disagree (e.g., energy-based pauses vs `ffmpeg silencedetect`), do not pick one silently; reconcile and then spot-check.

```python
# a_segments / b_segments: list[dict] with {start,end} floats/ints
# Returns a merged list and a short disagreement summary.

def _norm(segs):
    out = []
    for s in segs:
        a, b = float(s["start"]), float(s["end"])
        if b > a:
            out.append((a, b))
    out.sort()
    return out

A, B = _norm(a_segments), _norm(b_segments)

tol = 0.5  # seconds; boundaries farther apart are a real disagreement
pairs = [(a, b) for a in A for b in B if abs(a[0]-b[0]) <= tol or abs(a[1]-b[1]) <= tol]
need_review = (len(pairs) == 0) and (len(A) + len(B) > 0)
print({"need_review": need_review, "a": len(A), "b": len(B), "paired": len(pairs)})
```

Decision rule: if the opening boundary or a sample of pauses do not agree within tolerance across detectors, pause and verify content (short audio probes) before producing the final `remove_segments.json`.

Read references/detector-reconciliation.md when you have two (or more) candidate segment lists for the same phenomenon (opening or pauses) or when boundaries look coarse/implausible. Skip when only one detector was used end-to-end and you already spot-checked boundaries.

## Dependencies

- Python 3.11+

## Example

```bash
# Combine segments from multiple detectors
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments initial_silence.json pauses.json \
    --output all_segments.json
```

## Notes

- Segments are sorted by start time
- Compatible with video-processor --remove-segments input
- All input files must have `segments` array
