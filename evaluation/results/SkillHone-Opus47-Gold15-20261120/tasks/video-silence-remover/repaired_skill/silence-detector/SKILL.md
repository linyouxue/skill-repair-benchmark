---
name: silence-detector
description: Detect the initial opening / pre-roll segment in audio or video by locating the first clear energy step. Use when you need to find the boundary between a recording's opening (title slides, intro music, static-frame noise) and its main content, whether the opening is quieter OR louder than the content.
---

# Silence / Opening Detector

Detects the opening by scanning the smoothed per-second energy for the
*first local step* that is both large enough and sustained afterwards.
This handles both common opening shapes:

- A quiet pre-roll that ends when speech begins (energy rises).
- A noisy opening (intro music, static-frame hum) that ends when the
  teaching content begins (energy drops).

The detector only reports an opening when the local step clears
`min_change_ratio` AND the post-boundary data stays near the new regime
for at least `sustain_seconds`; otherwise it reports an empty segments
list.

## Use Cases

- Finding the opening in lecture / teaching recordings
- Locating title cards, intros, or setup periods
- Picking the boundary at which pause-detection should start

## Usage

```bash
python3 /root/.claude/skills/silence-detector/scripts/detect_silence.py \
    --energies /path/to/energies.json \
    --output /path/to/opening.json
```

### Parameters

- `--energies`: Path to energy JSON file (from `energy-calculator`)
- `--output`: Path to output JSON file
- `--smoothing-window`: Moving-average window in seconds (default: 5)
- `--min-opening`: Minimum opening length to consider in seconds (default: 1)
- `--max-opening-fraction`: Hard cap on the opening as fraction of total track (default: 0.3)
- `--min-change-ratio`: Minimum relative change between local before/after medians required to accept the boundary (default: 0.35)
- `--local-window`: Seconds used on each side of a candidate boundary for the local median comparison (default: 20)
- `--sustain-seconds`: Seconds after the boundary that must track the new median (default: 10)

### Output Format

```json
{
  "method": "energy_local_step",
  "segments": [
    {"start": 0, "end": 75, "duration": 75}
  ],
  "total_segments": 1,
  "total_duration_seconds": 75,
  "parameters": { "...": "..." },
  "analysis": {
    "track_length_seconds": 600,
    "best_boundary_seconds": 75,
    "best_change_ratio": 0.42,
    "before_median": 1300.0,
    "after_median": 510.0
  }
}
```

## How It Works

1. Smooth the per-second energies with a short moving average.
2. Walk forward through candidate boundaries ``t`` inside the allowed
   opening region (``min_opening`` .. ``max_opening_fraction * track``).
3. For each ``t``, compare the median of a short window just before ``t``
   with the median of a short window just after ``t`` (``local_window``
   seconds on each side).
4. Accept the first ``t`` whose relative change
   ``|before - after| / max(before, after)`` clears ``min_change_ratio``
   AND whose new regime is sustained for ``sustain_seconds`` after ``t``.
5. Within a short refinement span, snap to the sharpest step so the
   boundary lands on the exact edge.
6. If no candidate qualifies, report no opening (empty segments).

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `smoothing_window` | Snappier, noisier detection | Smoother but may dilute short transitions |
| `max_opening_fraction` | Tighter cap, safer against over-trimming | Allows a longer opening |
| `min_change_ratio` | Reports fainter openings | Only large, clear transitions accepted |
| `local_window` | More reactive to local shape | Requires change to span a wider neighbourhood |
| `sustain_seconds` | Accepts quick transitions | Requires long post-boundary consistency |

## Dependencies

- Python 3.11+
- numpy

## Example

```bash
python3 /root/.claude/skills/silence-detector/scripts/detect_silence.py \
    --energies energies.json \
    --output opening.json
```

## Notes

- Requires energy data from the `energy-calculator` skill.
- Works whether the opening is quieter or louder than the body — picking
  the FIRST qualifying local step avoids being pulled into a later,
  bigger within-content swing.
- Reports only the opening-to-content transition. Any quiet setup period
  immediately after the opening is left to the pause-detector, so it is
  described with its natural granularity instead of being swallowed into
  an over-long opening segment.
- Returns an empty `segments` list when no clear transition is found —
  in that case downstream pause detection should start at ``0``.
- `max_opening_fraction` guards against swallowing real content when the
  energy profile is noisy or atypical.
- Output format is compatible with `segment-combiner`.
