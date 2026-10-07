---
name: pause-detector
description: Detect pauses and silence in audio using local dynamic thresholds. Use when you need to find natural pauses in lectures, board-writing silences, or breaks between sections. Uses local context comparison to propose pause candidates for review.
---

# Pause Detector

Detects pauses and low-energy segments using local dynamic thresholds on pre-computed energy data. This compares energy to surrounding context. Low energy relative to nearby speech proposes a pause candidate; it does not by itself establish silence.

## Use Cases

- Detecting natural pauses in lectures
- Finding board-writing silences
- Identifying breaks between sections

## Usage

```bash
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies /path/to/energies.json \
    --audio /path/to/audio.wav \
    --output /path/to/pauses.json
```

### Parameters

- `--energies`: Path to energy JSON file (from energy-calculator)
- `--audio`: Extracted 16-bit mono PCM WAV from the same recording (required)
- `--output`: Path to output JSON file
- `--start-time`: Start analyzing from this second (default: 0)
- `--threshold-ratio`: Ratio of local average for low energy (default: 0.5)
- `--min-duration`: Minimum pause duration in seconds, inclusive (default: 2)
- `--window-size`: Local average window size (default: 30)

### Output Format

```json
{
  "method": "local_dynamic_threshold_with_audio_audit",
  "segments": [
    {"start": 610, "end": 613, "duration": 3},
    {"start": 720, "end": 724, "duration": 4}
  ],
  "total_segments": 2,
  "total_duration_seconds": 7,
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
6. Audit each candidate against 20 ms RMS frames from the original audio; require at least two-thirds of its frames in the recording-derived quiet class. Save the cutoff and every accepted/rejected candidate in audio_audit.

## Dependencies

- Python 3.11+
- numpy
- scipy

## Example

```bash
# Set OPENING_END from the opening detector result, then detect long pauses
python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
    --energies energies.json \
    --audio audio.wav \
    --start-time "$OPENING_END" \
    --output pauses.json

# Review the returned candidates before combining them with the opening.
```

## Preserve teaching content when selecting pauses

The script uses one-second energy bins to propose candidates with an inclusive
two-second minimum. These are approximate boundaries: increasing the minimum
alone can discard real pauses while leaving longer quiet speech.

Pass the extracted audio to the detector. It fits two RMS levels in log space
after the opening, then requires a robust two-thirds majority of 20 ms frames
below the midpoint of those levels. This rejects candidates whose average only
looks low relative to louder neighbors while tolerating occasional transient
sounds. The cutoff is estimated from this recording, not a universal amplitude.

Read audio_audit before combining segments: each candidate has its measured
quiet-frame fraction and an acceptance decision. Only accepted candidates appear
in segments. This check is still an energy heuristic; compare uncertain
candidates with adjacent audio and preserve audible teaching. Keep the audit JSON
with the final outputs so decisions remain reviewable. Use one-second
energy-calculator windows for this script's candidate timestamps.
Keep the opening detector's result separate from the pause-duration rule.
Avoid widening a cut across an intervening audible interval simply to combine
nearby candidates. Render the video and generate the report from the same final,
sorted, non-overlapping removal list.

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `threshold_ratio` | Lower cutoff; fewer low-energy candidates | Higher cutoff; more low-energy candidates |
| `min_duration` | Shorter pauses | Longer pauses only |
| `window_size` | Local context | Broader context |

## Notes

- Requires energy data from energy-calculator skill
- Use --start-time to skip detected opening
- Local threshold adapts to varying speaker volume
