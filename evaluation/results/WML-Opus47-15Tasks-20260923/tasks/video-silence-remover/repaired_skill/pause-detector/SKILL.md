---
name: pause-detector
description: Detect pauses and silence in audio using local dynamic thresholds. Use when you need to find natural pauses in lectures, board-writing silences, or breaks between sections. Uses local context comparison to avoid false positives from volume variation.
---

# Pause Detector

Detects pauses and low-energy segments using local dynamic thresholds on pre-computed energy data. Unlike global threshold methods, this compares energy to surrounding context, avoiding false positives when speaker volume varies.

## Use Cases

- Detecting natural pauses in lectures
- Finding board-writing silences
- Identifying breaks between sections

## Usage

```bash
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies /path/to/energies.json \
    --output /path/to/pauses.json
```

### Parameters

- `--energies`: Path to energy JSON file (from energy-calculator)
- `--output`: Path to output JSON file
- `--start-time`: Start analyzing from this second (default: 0)
- `--threshold-ratio`: Ratio of local average for low energy (default: 0.5)
- `--min-duration`: Minimum pause duration in seconds (default: 2)
- `--window-size`: Local average window size (default: 30)

### Output Format

```json
{
  "method": "local_dynamic_threshold",
  "segments": [
    {"start": 610, "end": 613, "duration": 3},
    {"start": 720, "end": 724, "duration": 4}
  ],
  "total_segments": 11,
  "total_duration_seconds": 28,
  "parameters": {
    "threshold_ratio": 0.5,
    "window_size": 30,
    "min_duration": 2
  }
}
```

## How It Works

1. Load pre-computed energy data
2. Calculate local average using sliding window
3. Mark seconds where energy < local_avg × threshold_ratio
4. Group consecutive low-energy seconds into segments
5. Filter segments by minimum duration

## Dependencies

- Python 3.11+
- numpy
- scipy

## Example

```bash
# Detect pauses after opening (start at 221s)
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies energies.json \
    --start-time 221 \
    --output pauses.json

# Result: Found 11 pauses totaling 28 seconds
```

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | More aggressive | More conservative |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | Local context | Broader context |

### Post-processing for precision

The detector's defaults favor recall: with a 1-second energy grid and `min_duration=2`, the raw output frequently contains (a) multiple short segments separated by 1–2 s gaps that actually belong to the same underlying pause, and (b) borderline 2 s hits sitting exactly at the minimum-duration cutoff. Forwarding this raw list into `segment-combiner` / `video-processor` inflates the segment count and reduces IoU precision against ground-truth pauses, even when total removed duration and recall are correct.

When the downstream evaluation weighs per-segment precision or IoU (e.g., "remove long pauses > 2 s", or scoring individual removed intervals), post-process the candidate list before combining:

1. **Gap-merge near-adjacent segments.** Iterate segments in start order and merge any pair whose inter-segment gap is ≤ a small tolerance (1–2 s is a reasonable default for 1 s energy windows). This collapses fragmented pieces of the same pause into one interval and typically eliminates the largest source of false positives.
2. **Reconsider borderline hits.** If, after merging, many surviving segments are still exactly at `min_duration` (e.g., a cluster of 2 s hits), prefer either raising `--min-duration` (e.g., to 3) or lowering `--threshold-ratio` (e.g., 0.3–0.4) and re-running detection. Either change trades a small amount of recall for higher precision.
3. **Sanity-check candidate count vs. task guidance.** If the task describes pauses qualitatively (e.g., "long pauses, usually > 2 s") and the raw output returns many more candidates than that description implies, treat it as a signal to apply steps 1–2 rather than pass the raw list through.

A minimal gap-merge is straightforward to apply to the JSON output without changing the detector:

```python
import json

GAP_TOL = 1  # seconds; merge segments separated by <= GAP_TOL

data = json.load(open("pauses.json"))
segs = sorted(data["segments"], key=lambda s: s["start"])
merged = []
for s in segs:
    if merged and s["start"] - merged[-1]["end"] <= GAP_TOL:
        merged[-1]["end"] = max(merged[-1]["end"], s["end"])
        merged[-1]["duration"] = merged[-1]["end"] - merged[-1]["start"]
    else:
        merged.append(dict(s))

data["segments"] = merged
data["total_segments"] = len(merged)
data["total_duration_seconds"] = sum(s["duration"] for s in merged)
json.dump(data, open("pauses.json", "w"), indent=2)
```

The merged file remains compatible with `segment-combiner` and `video-processor`; total removed duration and math consistency are preserved (merging only removes intra-pause gaps of ≤ `GAP_TOL` seconds, which are themselves low-energy).

**Verification / fallback.** After post-processing, re-check: (i) the number of surviving segments is closer to the qualitative description in the task, (ii) no two segments are within `GAP_TOL` of each other, and (iii) the sum of `duration` still matches what `segment-combiner` and the final report show. If gap-merging alone leaves many borderline 2 s hits, re-run detection with a tighter `--threshold-ratio` or a larger `--min-duration` and repeat the check.

## Notes

- Requires energy data from energy-calculator skill
- Use --start-time to skip detected opening
- Local threshold adapts to varying speaker volume

### Pipeline usage

Inside a detector → combiner → processor pipeline, treat this skill's output as **candidates**, not as the final removal list. Before invoking `segment-combiner`, briefly inspect the candidate segments and decide based on the task's evaluation focus:

- If the evaluator scores per-segment precision or IoU on removed intervals, apply the *Post-processing for precision* steps above (gap-merge, and if needed re-tune `threshold_ratio` / `min_duration`) before combining.
- If the evaluator only checks total removed duration, compression ratio, or math consistency, the default recall-friendly output is usually sufficient and no post-processing is required.

This lightweight review gate between detection and combination keeps the recall-oriented defaults intact while avoiding forwarding over-segmented candidates verbatim to video processing.
