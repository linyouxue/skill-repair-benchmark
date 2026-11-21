#!/usr/bin/env python3
"""
Silence detector - finds initial silence segment using energy data.
Detects low-energy periods at the start of audio (e.g., title slides, setup time).

Timebase contract
-----------------
- Input `energies` is assumed to be a sequence of per-window RMS energies produced by
  energy-calculator, where index i corresponds to the window covering:
      [i * window_seconds, (i+1) * window_seconds)
  (typically window_seconds=1).

- This script returns `silence_end` as an integer index in the SAME timebase:
  the first window index whose *smoothed* energy exceeds the threshold.

- Output segment uses half-open interval semantics:
      {"start": 0, "end": silence_end}
  meaning windows [0, silence_end) are considered removable as initial silence.

Smoothing alignment
-------------------
When smoothing is enabled, we use a centered moving average so that the smoothed
value at index i aligns with the original energy index i. This avoids the common
"valid" convolution timestamp shift.
"""

import argparse
import json

import numpy as np


def _centered_moving_average(x: np.ndarray, window: int) -> np.ndarray:
    """Centered moving average aligned to original indices.

    Uses edge padding so output length equals input length and index i corresponds
    to the neighborhood centered at i.

    For window <= 1, returns x unchanged.
    """

    if window <= 1 or len(x) == 0:
        return x

    # Ensure odd window for true centering; if even, we still center by padding
    # asymmetrically (left=floor, right=ceil).
    left = (window - 1) // 2
    right = window - 1 - left

    padded = np.pad(x, (left, right), mode="edge")
    kernel = np.ones(window, dtype=np.float32) / float(window)
    return np.convolve(padded, kernel, mode="valid")


def detect_initial_silence(energies, threshold_multiplier=1.5, initial_window=60, smoothing_window=30):
    """Detect initial silence using energy threshold method.

    Returns:
      silence_end (int): first index i where smoothed_energy[i] > threshold.
      analysis (dict): diagnostic values.
    """

    energies = np.asarray(energies, dtype=np.float32)
    if energies.size == 0:
        return 0, {"initial_avg": 0.0, "threshold": 0.0, "note": "empty energies"}

    # Calculate initial average (baseline from likely-silent period)
    baseline_n = int(min(max(initial_window, 1), len(energies)))
    initial_avg = float(np.mean(energies[:baseline_n]))

    # Calculate threshold
    threshold = float(initial_avg * float(threshold_multiplier))

    # Apply centered moving average to smooth (aligned to original indices)
    smoothing_window = int(max(smoothing_window, 1))
    smoothed = _centered_moving_average(energies, smoothing_window)

    # Find where smoothed energy exceeds threshold (end of initial silence)
    silence_end = 0
    for i, val in enumerate(smoothed):
        if float(val) > threshold:
            silence_end = int(i)
            break

    analysis = {
        "initial_avg": initial_avg,
        "threshold": threshold,
        "baseline_seconds_used": baseline_n,
        "smoothing_window": smoothing_window,
        "smoothed_alignment": "centered_same_length",
    }
    return silence_end, analysis


def main():
    parser = argparse.ArgumentParser(description="Detect initial silence from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--threshold-multiplier", type=float, default=1.5, help="Threshold multiplier (default: 1.5)")
    parser.add_argument("--initial-window", type=int, default=60, help="Initial window for baseline (default: 60)")
    parser.add_argument("--smoothing-window", type=int, default=30, help="Smoothing window (default: 30)")

    args = parser.parse_args()

    print(f"Detecting initial silence from: {args.energies}")
    print(
        "Parameters: "
        f"multiplier={args.threshold_multiplier}, initial={args.initial_window}s, smoothing={args.smoothing_window}s"
    )

    # Load energy data
    with open(args.energies) as f:
        energy_data = json.load(f)

    energies = energy_data["energies"]
    total_seconds = energy_data.get("total_seconds")

    # Detect initial silence
    silence_end, analysis = detect_initial_silence(
        energies,
        args.threshold_multiplier,
        args.initial_window,
        args.smoothing_window,
    )

    # Build segments list (half-open interval [start,end))
    segments = []
    if silence_end > 0:
        segments.append({"start": 0, "end": silence_end, "duration": silence_end})

    # Save result
    result = {
        "method": "energy_threshold",
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": silence_end if silence_end > 0 else 0,
        "parameters": {
            "threshold_multiplier": args.threshold_multiplier,
            "initial_window": args.initial_window,
            "smoothing_window": args.smoothing_window,
        },
        "analysis": analysis,
        "timebase": {
            "unit": "energy_window_index",
            "window_seconds": energy_data.get("window_seconds", 1),
            "interval_semantics": "half_open_[start,end)",
            "note": "Indices align to energy-calculator windows; for window_seconds=1, indices are seconds.",
        },
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    # Prefer printing in seconds when available
    ws = float(energy_data.get("window_seconds", 1))
    print(f"\nInitial silence detected: {silence_end * ws:.2f}s (index={silence_end})")
    if total_seconds is not None:
        print(f"Total analyzed duration: {float(total_seconds):.2f}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
