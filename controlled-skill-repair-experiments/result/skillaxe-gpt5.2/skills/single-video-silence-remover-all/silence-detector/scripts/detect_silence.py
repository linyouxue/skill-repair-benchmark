#!/usr/bin/env python3
"""
Silence detector - finds initial silence segment using energy data.
Detects low-energy periods at the start of audio (e.g., title slides, setup time).

IMPORTANT TIMESTAMP CONVENTION
- Input energies are per-window values from energy-calculator (default: 1 second windows).
- Returned silence_end is expressed in the SAME time base as energies indices (seconds when window_seconds=1).
- When smoothing is enabled, the smoothed series is aligned to the *end* of each smoothing window.
  That is, smoothed[k] summarizes energies[k : k+smoothing_window] and is mapped to time index (k+smoothing_window).
  This avoids returning a boundary that is early by (smoothing_window-1) seconds.
"""

import argparse
import json

import numpy as np


def _moving_average_valid(x: np.ndarray, window: int) -> np.ndarray:
    """Valid moving average (length N-window+1)."""
    kernel = np.ones(window, dtype=np.float64) / float(window)
    return np.convolve(x, kernel, mode="valid")


def detect_initial_silence(energies, threshold_multiplier=1.5, initial_window=60, smoothing_window=30):
    """Detect initial silence using energy threshold method.

    Returns:
      silence_end (int): boundary time index in the same units as energies index.
                        Segment [0, silence_end) is considered removable opening/silence.
      analysis (dict): diagnostic values.

    Notes on smoothing alignment:
      If smoothing_window=W and we use a valid moving average, smoothed[k] corresponds to
      energies[k:k+W]. We map that to time index k+W (window end) to avoid early boundaries.
    """

    energies = np.asarray(energies, dtype=np.float64)
    n = len(energies)
    if n == 0:
        return 0, {"initial_avg": 0.0, "threshold": 0.0, "alignment": "none"}

    # Calculate initial average (baseline from likely-silent period)
    baseline_n = min(int(initial_window), n)
    initial_avg = float(np.mean(energies[:baseline_n]))

    # Calculate threshold
    threshold = float(initial_avg * float(threshold_multiplier))

    # Apply moving average to smooth
    alignment = "none"
    if smoothing_window and smoothing_window > 1 and n >= smoothing_window:
        W = int(smoothing_window)
        smoothed = _moving_average_valid(energies, W)
        alignment = f"valid_ma_end_aligned_W={W}"

        # Find first window whose average exceeds threshold.
        # Map index k to boundary at end of window: k+W.
        silence_end = 0
        for k, val in enumerate(smoothed):
            if val > threshold:
                silence_end = k + W
                break
        silence_end = int(min(max(silence_end, 0), n))
    else:
        # No smoothing (or too-short signal): use raw energies, boundary at first exceed.
        silence_end = 0
        for i, val in enumerate(energies):
            if val > threshold:
                silence_end = i
                break
        silence_end = int(min(max(silence_end, 0), n))

    return silence_end, {"initial_avg": initial_avg, "threshold": threshold, "alignment": alignment}


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

    # Detect initial silence
    silence_end, analysis = detect_initial_silence(
        energies,
        args.threshold_multiplier,
        args.initial_window,
        args.smoothing_window,
    )

    # Build segments list (half-open interval [start, end))
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
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nInitial silence detected: {silence_end}s ({silence_end/60:.2f} min)")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
