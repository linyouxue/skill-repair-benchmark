#!/usr/bin/env python3
"""
Silence detector - finds initial silence segment using energy data.
Detects low-energy periods at the start of audio (e.g., title slides, setup time).
"""

import argparse
import json

import numpy as np


def detect_initial_silence(energies, threshold_multiplier=1.5, initial_window=60, smoothing_window=30):
    """Detect initial silence using an energy threshold and optional smoothing.

    The input `energies` is expected to be an array-like sequence where index `i`
    corresponds to the energy for second `i` (i.e., `window_seconds=1` from the
    energy-calculator default).

    When smoothing is enabled, we compute a moving-average with `mode="valid"`.
    The resulting smoothed value at index `i` summarizes the window
    `energies[i : i + smoothing_window]`. To map this back to a timestamp on the
    original timeline, we use the *center* of that window.
    """

    energies = np.asarray(energies, dtype=float)
    if energies.size == 0:
        return 0, {"initial_avg": 0.0, "threshold": 0.0, "smoothing_offset": 0}

    # Calculate initial average (baseline from likely-silent period)
    baseline_n = min(max(int(initial_window), 1), int(energies.size))
    initial_avg = float(np.mean(energies[:baseline_n]))

    # Calculate threshold
    threshold = float(initial_avg * threshold_multiplier)

    # Apply moving average to smooth.
    # NOTE: With mode="valid", the smoothed series is shorter than the original.
    # We therefore track a timestamp offset so indices can be interpreted as
    # seconds on the original timeline.
    smoothing_offset = 0
    if smoothing_window and int(smoothing_window) > 1 and energies.size >= int(smoothing_window):
        w = int(smoothing_window)
        kernel = np.ones(w, dtype=float) / float(w)
        smoothed = np.convolve(energies, kernel, mode="valid")
        # Map smoothed index -> original seconds using window center.
        smoothing_offset = w // 2
    else:
        smoothed = energies

    # Find where smoothed energy exceeds threshold (end of initial silence)
    silence_end = 0
    for i, value in enumerate(smoothed):
        if float(value) > threshold:
            silence_end = int(i + smoothing_offset)
            break

    # Clamp to a valid boundary on the original timeline.
    silence_end = max(0, min(silence_end, int(energies.size)))

    return silence_end, {
        "initial_avg": initial_avg,
        "threshold": threshold,
        "smoothing_offset": int(smoothing_offset),
    }


def main():
    parser = argparse.ArgumentParser(description="Detect initial silence from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--threshold-multiplier", type=float, default=1.5, help="Threshold multiplier (default: 1.5)")
    parser.add_argument("--initial-window", type=int, default=60, help="Initial window for baseline (default: 60)")
    parser.add_argument("--smoothing-window", type=int, default=30, help="Smoothing window (default: 30)")

    args = parser.parse_args()

    print(f"Detecting initial silence from: {args.energies}")
    print(f"Parameters: multiplier={args.threshold_multiplier}, initial={args.initial_window}s, smoothing={args.smoothing_window}s")

    # Load energy data
    with open(args.energies) as f:
        energy_data = json.load(f)

    energies = energy_data["energies"]
    total_seconds = energy_data["total_seconds"]

    # Detect initial silence
    silence_end, analysis = detect_initial_silence(energies, args.threshold_multiplier, args.initial_window, args.smoothing_window)

    # Build segments list (same format as pause detector)
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
