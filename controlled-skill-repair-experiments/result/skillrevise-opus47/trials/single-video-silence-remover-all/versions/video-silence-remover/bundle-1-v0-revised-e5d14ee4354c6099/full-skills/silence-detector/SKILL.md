---
name: silence-detector
description: Detect the non-teaching opening prefix of a recording from pre-computed per-second energy data. The opening may be literally silent OR noisy static; the detector must handle both and validate its own result before returning.
---

# Silence / Opening Detector

Finds the boundary where the opening prefix ends and sustained teaching content begins. Does NOT assume the opening is low-energy; the task family explicitly includes noisy static openings.

## Contracts

- Input: energies.json with a per-second energy array (index i == second i).
- Output: silence.json with
  ```
  {
    "method": "<primary|fallback_frame_drop|fallback_conservative>",
    "segments": [{"start": <sec>, "end": <sec>, "duration": <sec>}],
    "total_segments": <int>,
    "total_duration_seconds": <number>,
    "parameters": { ... },
    "validation": {"plausible": <bool>, "reason": "<string>"}
  }
  ```
- Units: seconds (float). Boundary convention: inclusive start, exclusive end. Smoothing window is specified in seconds and must match the energy index unit.
- At most one opening segment is returned (segments has length 0 or 1).

## Workflow

1. Load energies and compute total_duration = len(energies).
2. Discover the energy regime, do not trust fixed defaults:
   - Compute global median and MAD of the series.
   - Compute a smoothed series (centered moving average, window = max(5, round(0.03 * total_duration))).
3. Candidate boundary detection, try in order and stop at the first that passes validation:
   a. Drop-into-content: find the earliest index where the smoothed energy transitions to a sustained regime that is DIFFERENT from the prefix regime (either a sustained drop below prefix median, or a sustained rise above, held for >= 10s).
   b. Low-to-high rise: legacy mode. Only use when prefix MAD is small (prefix is quiet, not noisy); find first index where smoothed energy exceeds prefix_median + k * prefix_MAD, with k discovered from the series (start k=3, lower if no crossing).
4. Validation checkpoint (mandatory):
   - plausibility: boundary <= 0.2 * total_duration (reject otherwise).
   - regime change: mean energy in [boundary, boundary+30s] must differ from [0, boundary] by at least 1 robust-SD.
   - If either fails, mark primary attempt invalid and fall through.
5. Fallback branch (bounded, run only on validation failure):
   - If a frame-difference / variance signal is available alongside energies (optional sibling input), locate the first second where frame variance stabilizes and use that as boundary.
   - Else return a conservative short cut: boundary = min(10s, 0.05 * total_duration), method = "fallback_conservative", plausible = true, reason records the fallback.
6. Write silence.json with the chosen method, parameters actually used (not hard-coded defaults), and the validation record.

## Parameter Discovery

Do not hard-code 1.5 / 60 / 30. Derive:
- smoothing_window_sec: max(5, round(0.03 * total_duration))
- regime_hold_sec: 10
- plausibility_cap_ratio: 0.2
- threshold multiplier k: start 3.0, decrease stepwise to 1.5 only if no crossing found; record final value in parameters.

Keep a literal only when the surrounding task family confirms it is invariant; otherwise log the chosen value.

## Inter-skill Notes

- pause-detector: its threshold_ratio is a multiplier on the LOCAL window median energy (not the global baseline). Document this when invoking from video-processor so the two detectors do not share a confused "ratio" meaning.
- segment-combiner: consumes segments in seconds with inclusive-start / exclusive-end; this detector emits the same convention.

## Dependencies

- Python 3.11+, numpy.

## Failure Modes To Guard Against

- Noisy static opening inflates a first-N-seconds baseline. Mitigation: do not treat the prefix as "known silent"; use regime-change detection.
- Agent trusting an implausibly long opening. Mitigation: plausibility_cap_ratio check and explicit validation field in output.
- Unit drift between smoothing window and energy index. Mitigation: both expressed in seconds; asserted at load.