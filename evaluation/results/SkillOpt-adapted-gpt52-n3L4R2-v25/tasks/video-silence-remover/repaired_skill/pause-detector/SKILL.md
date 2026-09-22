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



### Detection contract

`--min-duration` is a hard removal rule: only a contiguous low-energy run with measured duration of at least two seconds may be emitted. Local-ratio evidence alone is insufficient; use an adaptive noise floor or absolute floor as a second constraint, and require sustained low-energy windows. When energy timestamps are coarse, use overlapping/fine-grained analysis or conservatively move boundaries inward so quiet teaching audio is not removed.

### Output Format

```json
{
  "method": "local_dynamic_threshold_with_noise_floor",
  "segments": [
    {"start": 610, "end": 613, "duration": 3},
    {"start": 720, "end": 724, "duration": 4}
  ],
  "total_segments": 2,
  "total_duration_seconds": 7,
  "parameters": {
    "threshold_ratio": 0.5,
    "window_size": 30,
    "min_duration": 2,
    "timestamp_resolution": "fine_or_overlapping_windows"
  },
  "candidate_diagnostics": [
    {
      "raw_start": 609.5,
      "raw_end": 613.5,
      "trimmed_start": 610,
      "trimmed_end": 613,
      "duration": 3,
      "threshold": "record local ratio and adaptive/absolute noise floor",
      "status": "accepted"
    }
  ]
}
```

## How It Works

1. Load energy samples with their actual timestamps; prefer fine-grained or overlapping windows rather than assuming each sample represents exactly one second.
2. Estimate an adaptive noise floor from a robust low-percentile of nearby energy values, and combine it with a configured absolute floor when available. A sample is a low-energy candidate only when it is below both the local dynamic threshold (`local_average × threshold_ratio`) and the noise-floor criterion.
3. Group adjacent candidate samples into contiguous runs. Require the run to remain low energy for at least `min-duration` seconds; do not remove isolated low samples or short gaps between speech-like samples.
4. Treat any window containing speech-like energy as retained evidence. Split or reject a candidate run when energy rises above the conservative threshold instead of smoothing it into a removable interval.
5. Convert each qualifying run to a raw `[start, end]` interval using sample timestamps, then trim both boundaries inward by the local window half-width or another explicitly recorded safety margin. Never expand an interval into neighboring teaching audio.
6. Keep only intervals whose measured, post-trim duration is still at least two seconds. Emit the final intervals and diagnostics for every candidate so the raw run, thresholds, trim, and rejection reason are auditable.

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

## Notes

- Requires energy data from energy-calculator skill
- Use --start-time to skip detected opening
- Local threshold adapts to varying speaker volume


## Conservative Review Requirements

Before passing segments to a remover, inspect the emitted diagnostics. Each accepted segment must show a contiguous raw low-energy run, its local threshold and adaptive or absolute noise-floor value, the raw and inward-trimmed boundaries, and a post-trim duration of at least two seconds. Reject candidates with speech-like energy, uncertain timestamps, non-finite values, non-positive duration, or a post-trim duration below two seconds. Preserve short pauses even when they occur near a qualifying run unless the combined contiguous low-energy evidence independently satisfies the same rule.
