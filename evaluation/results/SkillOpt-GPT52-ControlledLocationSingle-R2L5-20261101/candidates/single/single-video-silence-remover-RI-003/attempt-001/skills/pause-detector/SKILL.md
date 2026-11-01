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
- `--threshold-ratio`: Low-energy cutoff **multiplier** relative to the local average (default: 0.5).
  - **Exact condition:** a second is marked low-energy when `energy < (local_avg * threshold_ratio)`.
  - **Monotonic behavior:** increasing `threshold_ratio` raises the cutoff, so **more** seconds satisfy the inequality (more aggressive pause detection / removal). Decreasing it lowers the cutoff, so **fewer** seconds are flagged (stricter; preserves more content).
  - Interactions: `local_avg` depends on `--window-size`; use `--min-duration` to suppress brief dips; use `--start-time` to ignore the opening/intro boundary before tuning the ratio.
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



### `threshold_ratio` (most important knob)

The detector flags low-energy seconds using `energy < (local_avg * threshold_ratio)`. Because the predicate is strict `<`, **higher `threshold_ratio` always produces the same-or-more low-energy seconds** (never fewer).

**Task-aligned tuning (teaching videos):**
- Start at **0.4–0.6** (often `0.5`).
- If long board-writing silences are **not** being removed, increase gradually (e.g., `0.5 → 0.6 → 0.65`).
- If quiet speech is being removed (soft voice, distant mic, writing while speaking), decrease (e.g., `0.5 → 0.45 → 0.4`).
- Pair with `--min-duration >= 2` to target “real” pauses and avoid cutting natural micro-pauses.

**Interactions / gotchas:**
- `--window-size`: larger windows make `local_avg` smoother (often fewer rapid on/off toggles); smaller windows track quick loudness changes and can over-trigger in dynamic speech.
- `--start-time`: set this to **just after the opening** (static/noise intro) so the local average is computed on teaching content; otherwise the intro can skew early thresholds.



### Practical guidance (lecture videos)

- Start with `--threshold-ratio 0.5`.
- Typical useful range: **~0.35–0.7**.
  - If you are **missing** obvious pauses/board-writing silences, **increase** the ratio (e.g., 0.55 → 0.65).
  - If you are **removing quiet teaching** (soft voice, mic far away), **decrease** the ratio (e.g., 0.5 → 0.4).
- Caution: when speaker loudness changes a lot, the local average will track the change; prefer small ratio adjustments and consider increasing `--window-size` for smoother context if you see oscillation.

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | Stricter (fewer pauses detected) | More aggressive (more pauses detected) |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | Local context | Broader context |

## Notes

- Requires energy data from energy-calculator skill
- Use `--start-time` to begin analysis **just after** the opening/intro boundary (so the local average and detected pauses reflect teaching content).
- Local threshold adapts to varying speaker volume
- `--min-duration` controls filtering of detected low-energy runs; if you see too many short “blips,” increase `--min-duration` (e.g., 2 → 3).
