---
name: pause-detector
description: Detect pauses/silence in audio using robust local thresholds on windowed RMS energy. Use when you need to remove long pauses in lectures while avoiding false positives from volume variation.
---

# Pause Detector

Detects pauses (low-energy regions) from pre-computed windowed RMS energy data. Unlike simple global thresholds, it uses a **local moving median baseline** plus an **absolute noise-floor gate**, which is more robust to varying speaker loudness.

This script reads `window_seconds` from the energy JSON, so it works correctly even if you compute energy with sub-second windows.

## Use Cases

- Detecting long pauses in lectures
- Finding low-energy board-writing sections
- Identifying breaks between sections

## Usage

```bash
python3 skills/pause-detector/scripts/detect_pauses.py \
    --energies /path/to/energies.json \
    --output /path/to/pauses.json
```

## Parameters

- `--energies`: Path to energy JSON file (from `energy-calculator`)
- `--output`: Path to output JSON file

Detection behavior:
- `--start-time`: Start analyzing from this time in seconds (default: `0`)
- `--min-duration`: Minimum pause duration in seconds (default: `2`)
- `--window-size`: Local baseline window size in seconds (default: `30`)
- `--threshold-ratio`: Mark a window as low if `energy < local_median * threshold_ratio` (default: `0.5`)

Noise-floor gating (reduces false positives):
- `--noise-floor-percentile`: Percentile used to estimate the noise floor of the analyzed region (default: `10`)
- `--noise-floor-multiplier`: Multiplier on that noise floor to form an absolute silence-ish threshold (default: `1.8`)
- `--global-cap-ratio`: Caps the absolute threshold to `global_median * ratio` so quiet speech is less likely to be removed (default: `0.5`)

Post-processing:
- `--merge-gap`: Merge detected pauses separated by ≤ this gap in seconds (default: `0`)
- `--smoothing-seconds`: Smooth energies over this many seconds before thresholding (default: `1.0`)
- `--no-allow-local-only`: Require BOTH local threshold and absolute noise-floor gate (more conservative; can reduce recall)
- `--round-ndigits`: Round start/end/duration values in the output JSON (default: `3`)

## Output Format

```json
{
  "method": "energy_local_median_with_noise_floor_gate",
  "segments": [
    {"start": 79.184, "end": 83.201, "duration": 4.017},
    {"start": 111.079, "end": 162.84, "duration": 51.761}
  ],
  "total_segments": 2,
  "total_duration_seconds": 55.778,
  "parameters": {
    "start_time_seconds": 0.0,
    "min_duration_seconds": 2.0,
    "window_size_seconds": 30.0,
    "threshold_ratio": 0.5,
    "noise_floor_percentile": 10.0,
    "noise_floor_multiplier": 1.8,
    "global_cap_ratio": 0.5,
    "merge_gap_seconds": 0.0,
    "round_ndigits": 3
  }
}
```

## How It Works

1. Loads energy windows and `window_seconds`
2. Computes a **moving median** baseline over a local window
3. Computes an **absolute threshold** from the noise floor (with a safety cap)
4. Marks windows as pauses when the energy is below both thresholds
5. Optionally smooths energies to reduce fragmentation
6. Groups consecutive windows into segments, filters by `min_duration`, and optionally merges close segments

## Dependencies

- Python 3.11+

Uses only the Python standard library (no numpy/scipy required).

## Notes

- Use `--start-time` to skip an opening segment detected by another detector.
- If you use sub-second energy windows (e.g., `--window-seconds 0.5`), this detector will still output correct times in seconds.
- For downstream processing:
  - Use `segment-combiner` to merge pause segments with an opening segment.
  - Use `video-processor` to remove those segments from the video.
