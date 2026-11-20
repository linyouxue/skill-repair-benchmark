---
name: pause-detector
description: Detect pauses and silence inside audio using combined local-dynamic and absolute-floor thresholds. Use when you need to find natural pauses in lectures, board-writing silences, or breaks between sections. Combines local context comparison with a whole-track silence floor to avoid both false positives from volume variation and false negatives on long truly-silent gaps.
---

# Pause Detector

Detects pauses and low-energy segments from pre-computed per-second energy
data. A second counts as "quiet" when either its energy is below
``local_avg * threshold_ratio`` or below an absolute silence floor derived
from a low quantile of the whole track. This dual criterion catches both
soft pauses in a quiet passage and long truly-silent gaps, while remaining
robust to speaker volume variation.

A small configurable ``merge_gap`` lets two quiet runs separated by a
brief transient (a single loud consonant, a key-click) merge into a single
pause, which keeps real pauses from being chopped into sub-threshold
fragments.

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

- `--energies`: Path to energy JSON file (from `energy-calculator`)
- `--output`: Path to output JSON file
- `--start-time`: Start analyzing from this second (default: 0)
- `--end-time`: Stop analyzing at this second (default: end of track)
- `--threshold-ratio`: Ratio of local average for the relative low-energy test (default: 0.5)
- `--min-duration`: Minimum pause duration in seconds (default: 2)
- `--window-size`: Local-average window size in seconds (default: 30)
- `--absolute-quantile`: Whole-track quantile used for the absolute silence floor (default: 0.15)
- `--absolute-margin`: Multiplier applied to the quantile floor (default: 1.1)
- `--merge-gap`: Bridge up to this many non-quiet seconds between quiet runs (default: 5)

### Output Format

```json
{
  "method": "local_dynamic_threshold_with_floor",
  "segments": [
    {"start": 610, "end": 613, "duration": 3},
    {"start": 720, "end": 724, "duration": 4}
  ],
  "total_segments": 2,
  "total_duration_seconds": 7,
  "parameters": { "...": "..." }
}
```

## How It Works

1. Load pre-computed energy data.
2. Compute a local moving average over ``window_size`` seconds.
3. Compute an absolute silence floor as the ``absolute_quantile`` quantile
   of the whole track multiplied by ``absolute_margin``.
4. Mark each second as quiet if it is below the local-relative threshold
   OR below the absolute floor.
5. Group consecutive quiet seconds into segments, allowing up to
   ``merge_gap`` non-quiet seconds between two quiet runs to count as a
   single pause.
6. Keep only segments whose duration ≥ ``min_duration``.

## Dependencies

- Python 3.11+
- numpy
- scipy

## Example

```bash
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies energies.json \
    --start-time 75 \
    --output pauses.json
```

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | Fewer, stricter pauses | More, more permissive pauses |
| `min_duration` | Shorter pauses allowed | Only longer pauses reported |
| `window_size` | Local context (adapts quickly) | Broader context (more stable) |
| `absolute_quantile` | Floor set at a quieter level | Floor set higher, more aggressive |
| `absolute_margin` | Tighter absolute floor | More permissive absolute floor |
| `merge_gap` | Each quiet run reported separately | Nearby quiet runs merged into one pause |

## Notes

- Requires energy data from the `energy-calculator` skill.
- Use ``--start-time`` to skip a detected opening (and optionally
  ``--end-time`` to skip a tail).
- Local threshold adapts to varying speaker volume; absolute floor catches
  long dead silence that the local threshold would miss.
- Output format is compatible with `segment-combiner`.
- For teaching content the task usually targets pauses longer than
  ~2 seconds; keep ``min_duration`` ≥ 2 to preserve natural speech rhythm.
- If the body of the recording is itself quiet (e.g. writing on a board),
  reduce ``threshold_ratio`` and/or ``absolute_margin`` so the quiet
  speech sections are not labelled as pauses wholesale.
