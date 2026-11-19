---
name: silence-detector
description: Detect an initial low-content "opening" segment using windowed RMS energy. Use when you need to remove pre-roll silence/title-card time before the main content.
---

# Silence / Opening Detector

Detects an initial low-content segment (often an opening/title card) by analyzing pre-computed RMS energy windows.

Compared to a naive threshold on raw energy:
- Uses a **robust baseline** (percentile/median) over the early portion
- Uses a **centered smoothing window**
- Requires **sustained** energy above threshold before declaring the opening ended

The detector reads `window_seconds` from the energy JSON, so it works even if you compute energy with sub-second windows.

## Usage

```bash
python3 skills/silence-detector/scripts/detect_silence.py \
  --energies /path/to/energies.json \
  --output /path/to/opening.json
```

## Parameters

- `--search-max`: Search at most this many seconds from the start (default: `120`)
- `--baseline-seconds`: Seconds used to estimate the baseline energy (default: `30`)
- `--baseline-percentile`: Percentile used as baseline (default: `50` = median)
- `--smoothing-seconds`: Smoothing window in seconds (default: `3`)
- `--threshold-multiplier`: Threshold multiplier over baseline (default: `2.0`)
- `--sustain-seconds`: Require energy above threshold for this long (default: `2.0`)
- `--min-opening`: Minimum opening length in seconds (default: `0`)
- `--max-opening`: Maximum opening length in seconds (default: `180`)
- `--round-ndigits`: Round output values (default: `3`)

## Output Format

```json
{
  "method": "energy_opening_threshold_sustained",
  "segments": [
    {"start": 0.0, "end": 12.345, "duration": 12.345}
  ],
  "total_segments": 1,
  "total_duration_seconds": 12.345,
  "parameters": {
    "search_max_seconds": 120.0,
    "baseline_seconds": 30.0,
    "smoothing_seconds": 3.0,
    "threshold_multiplier": 2.0,
    "baseline_percentile": 50.0,
    "sustain_seconds": 2.0,
    "min_opening_seconds": 0.0,
    "max_opening_seconds": 180.0,
    "round_ndigits": 3
  }
}
```

## Notes

- Works best when the opening has noticeably lower audio energy than the main content.
- If no clear transition is found, the detector returns an empty `segments` list.
- Output format is compatible with `segment-combiner` and `video-processor`.
