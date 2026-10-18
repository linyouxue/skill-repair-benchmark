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



## Recommended Normalization (best practice)

When combining outputs from multiple detectors (e.g., **opening** + **pause** detectors), do **not** just concatenate lists. Normalize first to avoid fragmented/overlapping segments that hurt downstream cutting quality and IoU-based evaluation.

### Normalization steps (endorsed)

1. **Load all segments** from all inputs.
2. **Coerce types**: ensure `start`/`end` are floats in seconds.
3. **Clamp to media bounds**: `start = max(0, start)`, `end = min(video_duration, end)`.
4. **Ensure valid intervals**: drop any segment where `end <= start`.
5. **Optional padding** (seconds): expand cuts slightly to remove residual silence:
   - `start = max(0, start - pad_start)`
   - `end = min(video_duration, end + pad_end)`
6. **Deduplicate & resolve detector overlap**:
   - If you have an explicit opening segment, **remove or clip** pauses that fall **inside** the opening to avoid double-counting and fragmentation.
7. **Sort by start time**.
8. **Merge overlaps and near-adjacent segments** using a configurable **merge-gap** (seconds):
   - If `next.start <= current.end + merge_gap`, merge into `[current.start, max(current.end, next.end)]`.
9. **Drop tiny segments** below a minimum duration (e.g., `min_duration = 0.2–0.5s`), unless you intentionally want micro-cuts.
10. **Recompute duration** for each output segment: `duration = end - start`.

### Why this matters (IoU / precision / recall)

- **merge-gap too small** → many small segments → lower IoU per segment and more false positives (precision drops).
- **merge-gap too large** → merges across real teaching content → over-cutting (precision drops, content loss).
- **padding too large** → cuts into speech around pauses (precision/content retention drops).
- **no padding** → may leave short residual silence that looks like missed GT (recall drops).

Typical starting points for lecture videos:
- `merge_gap`: **0.3–1.0s**
- `pad_start/pad_end`: **0.05–0.2s** (often pad end a bit more than start)
- `min_duration`: **0.3–1.0s** (keep >2s pauses, drop micro noise)
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

## Dependencies

- Python 3.11+

## Example


### Example pipeline: combine `opening.json` + `pauses.json` into normalized `segments.json`

Assume:
- `opening.json` is from an opening detector (usually one segment starting at 0)
- `pauses.json` is from a pause detector (many segments)

```bash
python3 - <<'PY'
import json
from math import isfinite

opening_path = 'opening.json'
pauses_path  = 'pauses.json'
out_path     = 'segments.json'

# Tunables
MERGE_GAP   = 0.5   # seconds: merge segments separated by <= this gap
MIN_DUR     = 0.5   # seconds: drop segments shorter than this after merging
PAD_START   = 0.1   # seconds
PAD_END     = 0.1   # seconds
VIDEO_DUR   = None  # set if known; otherwise leave None to skip clamping

opening = json.load(open(opening_path)).get('segments', [])
pauses  = json.load(open(pauses_path)).get('segments', [])

# helper: normalize numeric times
def norm_seg(s):
    st = float(s['start']); en = float(s['end'])
    if not (isfinite(st) and isfinite(en)):
        return None
    if VIDEO_DUR is not None:
        st = max(0.0, min(st, VIDEO_DUR))
        en = max(0.0, min(en, VIDEO_DUR))
    # optional padding
    st = max(0.0, st - PAD_START)
    en = en + PAD_END if VIDEO_DUR is None else min(VIDEO_DUR, en + PAD_END)
    if en <= st:
        return None
    return {'start': st, 'end': en}

segs = []
for s in opening:
    ns = norm_seg(s)
    if ns: segs.append(ns)
for s in pauses:
    ns = norm_seg(s)
    if ns: segs.append(ns)

# filter/clip pauses inside opening (if opening exists)
# Strategy: if a pause overlaps the opening interval, clip it to only the part AFTER opening.
if segs and opening:
    op = norm_seg(opening[0])
    if op:
        op_s, op_e = op['start'], op['end']
        filtered = []
        for s in segs:
            # keep opening as-is
            if s is op:
                filtered.append(s)
                continue
            # if entirely inside opening, drop
            if s['start'] >= op_s and s['end'] <= op_e:
                continue
            # if overlaps opening, clip to outside
            if s['start'] < op_e and s['end'] > op_s:
                # keep only the part after opening (most common desired behavior)
                if s['end'] > op_e:
                    s = {'start': max(s['start'], op_e), 'end': s['end']}
                else:
                    continue
            if s['end'] > s['start']:
                filtered.append(s)
        segs = filtered

# sort and merge with MERGE_GAP
segs.sort(key=lambda x: x['start'])
merged = []
for s in segs:
    if not merged:
        merged.append(s)
        continue
    last = merged[-1]
    if s['start'] <= last['end'] + MERGE_GAP:
        last['end'] = max(last['end'], s['end'])
    else:
        merged.append(s)

# drop tiny segments and compute duration
out = []
for s in merged:
    dur = s['end'] - s['start']
    if dur >= MIN_DUR:
        out.append({'start': round(s['start'], 3), 'end': round(s['end'], 3), 'duration': round(dur, 3)})

json.dump({'segments': out, 'total_segments': len(out),
           'total_duration_seconds': round(sum(x['duration'] for x in out), 3)},
          open(out_path, 'w'), indent=2)
print('Wrote', out_path, 'segments=', len(out))
PY
```

This produces a single `segments.json` that is:
- sorted
- non-overlapping (after merge)
- de-fragmented (merge-gap)
- free of tiny/noisy cuts (min duration)
- consistent for downstream cutters and evaluators (durations recomputed)
```bash
# Combine segments from multiple detectors
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments initial_silence.json pauses.json \
    --output all_segments.json
```

## Notes

- This tool **combines** segments; for best results in multi-detector workflows, apply the **normalization** steps above (merge overlaps/near-adjacent, drop tiny segments, optional padding, and resolve overlaps between detectors).
- Always ensure output segments are **sorted**, **non-overlapping**, and have `duration = end - start`.
- If you have both an **opening** detector and a **pause** detector, avoid double-removing by **dropping or clipping** pauses that fall inside the opening segment.
- Compatible with `video-processor --remove-segments` input.
- All input files must have a `segments` array.
