---
name: silence-detector
description: Detect initial silence (pre-roll, title card, setup) in audio/video from pre-computed energy data. Returns a corrected timestamp for the end of the opening, with a plausibility fallback.
---

# Silence Detector

Finds the transition from an initial low-energy region (opening) to higher-energy content, and returns the transition expressed on the original timeline (not the smoothed-series index).

## When To Use

Use when:
- You have per-sample energy values with a known sample rate (seconds per sample).
- You need the end-time of an initial silence/opening segment on the original timeline.

Do not use for mid-video pause detection; use a dedicated pause detector for that.

## Inputs And Outputs

Call:

```bash
python3 scripts/detect_silence.py \
    --energies <energies.json> \
    --output <silence.json> \
    [--threshold-multiplier 1.5] \
    [--initial-window 60] \
    [--smoothing-window 30]
```

Output JSON:

```json
{
  "method": "energy_threshold",
  "segments": [{"start": 0, "end": <float>, "duration": <float>}],
  "total_segments": 0 | 1,
  "total_duration_seconds": <float>,
  "parameters": {"threshold_multiplier": 1.5, "initial_window": 60, "smoothing_window": 30},
  "notes": "<string, present when fallback or empty result was emitted>"
}
```

`segments` is empty when no reliable transition is found. Downstream consumers must handle the empty case.

## Procedure

1. Discover inputs:
   - Load the energies JSON. Confirm it contains an array of energies and a `seconds_per_sample` (or equivalent). If not present, derive from `duration / len(energies)` and record the assumption in `notes`.
2. Compute baseline:
   - Baseline = mean of first `initial_window` seconds of energies.
3. Smooth:
   - Apply a centered moving average of width `W = smoothing_window / seconds_per_sample` samples. Centered smoothing avoids systematic lag; if only a trailing moving average is available, you MUST compensate (see step 4).
4. Find crossing with timestamp correction:
   - Let `i*` be the first index where smoothed energy > `threshold_multiplier * baseline`.
   - If smoothing is trailing (not centered), map to timeline as `t = max(0, (i* - W // 2) * seconds_per_sample)`. If centered, `t = i* * seconds_per_sample`.
   - Refine `t`: scan raw energies in `[t - smoothing_window, t + smoothing_window]` and pick the earliest raw index where energy crosses `threshold_multiplier * baseline`. Prefer this refined timestamp when it is earlier than `t`.
5. Plausibility check (decision point):
   - Let `total = total_duration_seconds`. Define `MAX_OPENING = max(60.0, 0.15 * total)`.
   - If `t > MAX_OPENING`:
     - Retry once with `smoothing_window` halved and repeat steps 3-4.
     - If still `t > MAX_OPENING`, fall back to raw-energy crossing with no smoothing.
     - If still implausible, return `segments: []` and set `notes` to describe the fallback outcome. Never emit an implausible opening silently.
6. Emit result with corrected `t` as segment `end` and `start = 0`.

## Constraints

- Do not treat a smoothed-series index as a timeline timestamp without lag correction.
- Do not accept an opening longer than `MAX_OPENING` without running the retry/fallback path.
- Do not change `threshold_multiplier` purely to hit a target compression ratio; adjust only when raw-energy evidence contradicts the default.
- All paths in examples are illustrative; resolve the script path from the actual skill install location.

## How Smoothing Lag Arises

A trailing moving average of width `W` samples reports the crossing roughly `W/2` samples after the true transition. Without subtracting `W/2 * seconds_per_sample`, the reported opening is systematically too long. The refinement scan in step 4 further snaps the timestamp to the actual raw-energy rise.

## Dependencies

- Python 3
- numpy

## Checkpoints

- After step 4: log `i*`, raw crossing index, corrected `t`.
- After step 5: log whether plausibility passed, retried, fell back, or emitted empty.
- Consumer (e.g., video-processor) MUST validate that `end <= total_duration_seconds`, segments do not overlap other removed segments, and opening length is within `MAX_OPENING`; otherwise drop the opening segment before cutting.