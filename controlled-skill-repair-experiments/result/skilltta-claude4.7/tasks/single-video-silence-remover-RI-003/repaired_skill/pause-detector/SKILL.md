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
- `--threshold-ratio`: Local dynamic silence threshold (default: 0.5). See the detailed definition below.
- `--min-duration`: Minimum pause duration in seconds (default: 2, inclusive)
- `--window-size`: Local average window size in seconds (default: 30)

### Definition of `--threshold-ratio` (shared contract)

`threshold_ratio` is the **fraction of the local reference RMS below which a 1-second window is considered silent**. For this detector the reference is documented explicitly below. All three skills (`pause-detector`, `silence-detector`, `video-processor`) use the same wording for this shared definition, but each detector names its own reference level.

| Aspect | Value for pause-detector |
|---|---|
| Units | Linear ratio of RMS amplitudes (NOT dB, NOT dBFS). |
| Reference level | The **local sliding-window mean RMS** over `--window-size` seconds (default 30s), computed around each 1s window. |
| Semantic | A 1-second window `t` is "low energy" iff `energy[t] < local_mean[t] * threshold_ratio`. |
| Sane range | `0.3 – 0.6` for lecture audio with varying speaker volume. |
| Default | `0.5`. Lower → more aggressive (more pauses cut); higher → more conservative. |
| Interaction | Always combined with `--min-duration >= 2s` (inclusive) so short natural breathing pauses are preserved. |
| Not equivalent to | A fraction of peak RMS, a fraction of global median RMS, or an absolute dBFS value. If a caller wants dBFS semantics they must convert externally; this flag does not accept dB. |

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
2. Calculate local average RMS using a sliding window of `--window-size` seconds
3. Mark seconds where `energy < local_avg * threshold_ratio`
4. Group consecutive low-energy seconds into segments
5. Filter segments by `--min-duration` (inclusive)

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

| Parameter | Lower Value | Higher Value | Reference level |
|-----------|-------------|--------------|-----------------|
| `threshold_ratio` | More aggressive (cuts more) | More conservative (cuts less) | Local sliding-window mean RMS (`--window-size`) |
| `min_duration` | Shorter pauses allowed | Longer pauses only | — (duration gate, inclusive) |
| `window_size` | Reacts to local context | Reacts to broader context | — (defines the reference above) |

## Notes

- Requires energy data from energy-calculator skill
- Use `--start-time` to skip the detected opening (from silence-detector)
- Local threshold adapts to varying speaker volume
- Preserve pauses whose duration equals `--min-duration`; the threshold is inclusive
- `threshold_ratio` here is **not** the same quantity as silence-detector's `threshold_multiplier` — see that skill's "How it relates to pause-detector.threshold_ratio" note.
