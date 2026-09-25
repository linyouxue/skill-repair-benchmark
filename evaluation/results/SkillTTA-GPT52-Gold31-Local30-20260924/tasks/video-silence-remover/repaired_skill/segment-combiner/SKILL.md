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

- The bundled combiner sorts segments by start time but does **not** merge overlaps/adjacent segments or recompute durations. For reliable cutting and correct removed-time math, you should merge after combining.
- Compatible with video-processor `--remove-segments` input once segments are merged and `duration` is recomputed as `end - start`.
- All input files must have a `segments` array.

### Post-merge helper (recommended)

```bash
# Merge overlaps/adjacent segments and recompute duration
python3 - <<'PY'
import json

a='all_segments_raw.json'
b='all_segments.json'

data=json.load(open(a))
segs=[]
for s in data.get('segments', []):
    st=float(s['start']); en=float(s['end'])
    if en>st:
        segs.append([st,en])
segs.sort()

merged=[]
EPS=0.05  # merge gaps <= 50ms
for st,en in segs:
    if not merged or st>merged[-1][1]+EPS:
        merged.append([st,en])
    else:
        merged[-1][1]=max(merged[-1][1], en)

out=[{'start':st,'end':en,'duration':en-st} for st,en in merged]
res={'segments':out,'total_segments':len(out),'total_duration_seconds':sum(s['duration'] for s in out)}
json.dump(res, open(b,'w'), indent=2)
print('Wrote', b)
PY
```
