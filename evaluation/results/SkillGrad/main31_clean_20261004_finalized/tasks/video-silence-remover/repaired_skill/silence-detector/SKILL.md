---
name: silence-detector
description: Detect initial low-audio segments near the start of recordings using energy-based analysis and require plausibility checks plus content verification before accepting large removals.
---

# Silence Detector

Detects initial low-energy segments by analyzing pre-computed energy data. Because quiet speech, room tone, or noise suppression can look like “silence” in coarse RMS features, treat the detector output as a *proposal* that must pass a plausibility + content gate before you remove it.

## Use Cases

- Finding short pre-roll silence or setup time at the start
- Detecting title-card / waiting-to-start periods
- Proposing an opening cut point before pause detection runs later

## Usage

```bash
python3 /root/.claude/skills/silence-detector/scripts/detect_silence.py \
    --energies /path/to/energies.json \
    --output /path/to/silence.json
```

### Parameters

- `--energies`: Path to energy JSON file (from energy-calculator)
- `--output`: Path to output JSON file
- `--threshold-multiplier`: Energy threshold multiplier (default: 1.5)
- `--initial-window`: Seconds for baseline calculation (default: 60)
- `--smoothing-window`: Moving average window (default: 30)

### Output Format

```json
{
  "method": "energy_threshold",
  "segments": [
    {"start": 0, "end": 120, "duration": 120}
  ],
  "total_segments": 1,
  "total_duration_seconds": 120,
  "parameters": {
    "threshold_multiplier": 1.5,
    "initial_window": 60,
    "smoothing_window": 30
  }
}
```

## Opening removal acceptance gate (do this before cutting)

Use the energy-threshold segment as a candidate opening cut only if it passes both checks below.

```python
# segments: list[dict] with {start,end} in seconds
segment = next((s for s in segments if float(s.get("start", -1)) == 0.0), None)
max_default_opening = 60  # conservative; require stronger evidence above this

suspicious = (
    segment is not None
    and (float(segment["end"]) - float(segment["start"])) > max_default_opening
)

if suspicious:
    decision = "VERIFY_CONTENT"  # do not accept opening cut based on energy alone
else:
    decision = "OK_TO_TRY"  # still do a quick check if feasible
print(decision)
```

Decision rule: if the proposed opening removal starting at t=0 is longer than a conservative cap (≈30–60s), *assume it is wrong until proven otherwise*.

If suspicious, you must add **content verification** before producing `remove_segments.json`: spot-check multiple timestamps inside the proposed opening (early/mid/near-boundary) by extracting short audio snippets (and/or representative frames). Accept the cut only if those probes show no teaching/sustained speech and the boundary aligns with the first sustained speech-like region.

Do not “fix” an implausible opening estimate by switching heuristics and hardcoding a new cut time; instead, re-run one consistent detector with adjusted parameters (or a more robust detector), reconcile outputs, and then verify the boundary.

Read references/opening-cut-verification.md when the proposed opening cut from t=0 exceeds a conservative cap or when audio may contain quiet speech. Skip when you are only producing a diagnostic segments file and no content will be removed.

## How It Works

1. Load pre-computed energy data
2. Calculate baseline from first N seconds (assumed lower energy)
3. Apply smoothing with moving average
4. Find where smoothed energy exceeds baseline × multiplier

## Dependencies

- Python 3.11+
- numpy

## Parameters Tuning

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| threshold_multiplier | More sensitive | More conservative |
| initial_window | Shorter baseline | Longer baseline |
| smoothing_window | Less smoothing | More smoothing |

## Notes

- Requires energy data from energy-calculator skill
- Works best when the initial period has distinctly lower energy than speech
- Returns empty segments list if no clear transition is found
- Output format compatible with segment-combiner
