#!/usr/bin/env python3
"""
Silence detector - finds initial silence segment using energy data.
Detects low-energy periods at the start of audio (e.g., title slides, setup time).
"""

import argparse
import json

import numpy as np


def detect_initial_silence(
    energies,
    window_seconds,
    threshold_multiplier=1.5,
    initial_window=60,
    smoothing_window=30,
):
    """Detect initial silence using energy threshold method.

    Energy index k represents interval [k*window_seconds, (k+1)*window_seconds).
    Window parameters are specified in seconds and converted to frame counts.
    Uses causal smoothing to avoid look-ahead timestamp shifts.
    """

    energies = np.array(energies, dtype=float)

    initial_frames = max(1, int(round(initial_window / window_seconds)))
    smoothing_frames = max(1, int(round(smoothing_window / window_seconds)))

    # Calculate initial average (baseline from silent period)
    initial_avg = np.mean(energies[: min(initial_frames, len(energies))])

    # Calculate threshold
    threshold = initial_avg * threshold_multiplier

    # Apply causal moving average smoothing
    if len(energies) >= smoothing_frames and smoothing_frames > 1:
        kernel = np.ones(smoothing_frames, dtype=float) / smoothing_frames
        smoothed = np.convolve(energies, kernel, mode="full")[: len(energies)]
    else:
        smoothed = energies

    # Find first frame where energy exceeds threshold
    silence_end_frame = len(smoothed)
    for i, value in enumerate(smoothed):
        if value > threshold:
            silence_end_frame = i
            break

    silence_end_seconds = min(len(energies) * window_seconds, silence_end_frame * window_seconds)

    return silence_end_seconds, {
        "initial_avg": float(initial_avg),
        "threshold": float(threshold),
        "window_seconds": float(window_seconds),
        "initial_frames": int(initial_frames),
        "smoothing_frames": int(smoothing_frames),
        "silence_end_frame": int(silence_end_frame),
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


    window_seconds = energy_data.get("window_seconds")
    if window_seconds is None:
        if len(energies) == 0:
            raise ValueError("Cannot infer window_seconds from empty energies")
        window_seconds = total_seconds / len(energies)


    if not isinstance(energies, list) or len(energies) == 0:
        raise ValueError("Energy JSON must contain a non-empty 'energies' list")

    # Detect initial silence
    silence_end_seconds, diagnostics = detect_initial_silence(
        energies,
        window_seconds,
        args.threshold_multiplier,
        args.initial_window,
        args.smoothing_window,
    )
    silence_end_seconds = max(0.0, min(float(silence_end_seconds), float(total_seconds)))

    # Build segments list using half-open interval semantics: [start, end)
    segments = []
    if silence_end_seconds > 0:
        segments.append(
            {
                "start": 0,
                "end": silence_end_seconds,
                "duration": silence_end_seconds,
            }
        )

    # Save result
    result = {
        "method": "energy_threshold",
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": sum(segment["duration"] for segment in segments),
        "parameters": {
            "threshold_multiplier": args.threshold_multiplier,
            "initial_window": args.initial_window,
            "smoothing_window": args.smoothing_window,
            "window_seconds": window_seconds,
        },
        "diagnostics": {
            **diagnostics,
            "total_energy_frames": len(energies),
            "all_silent": silence_end_seconds >= total_seconds,
            "all_non_silent": silence_end_seconds == 0,
        },
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nInitial silence detected: {silence_end_seconds:.2f}s ({silence_end_seconds/60:.2f} min)")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
