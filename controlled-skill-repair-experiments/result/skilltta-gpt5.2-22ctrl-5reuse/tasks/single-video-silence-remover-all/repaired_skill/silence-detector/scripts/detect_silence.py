#!/usr/bin/env python3
""" 
Silence detector - finds initial silence segment using energy data.
Detects low-energy periods at the start of audio (e.g., title slides, setup time).

Contract:
- All times are in seconds (float).
- Segments are half-open intervals: [start, end)
- duration = end - start

This detector uses energies computed over fixed windows (energy-calculator's window_seconds).
"""

import argparse
import json
import math

import numpy as np


def _seconds_to_frames(seconds: float, window_seconds: float, *, minimum: int = 1) -> int:
    if window_seconds <= 0:
        raise ValueError("window_seconds must be > 0")
    if seconds is None:
        return minimum
    # ceil so "N seconds" means at least that much coverage
    return max(minimum, int(math.ceil(float(seconds) / float(window_seconds) - 1e-12)))


def _moving_average_centered_same(x: np.ndarray, window_frames: int) -> np.ndarray:
    """Centered moving average aligned to input indices (same length).

    Uses edge padding (mode='edge') and a valid convolution over the padded signal.
    """
    if window_frames <= 1 or len(x) == 0:
        return x.astype(np.float64, copy=False)

    w = int(window_frames)
    pad_left = w // 2
    pad_right = w - 1 - pad_left

    xpad = np.pad(x.astype(np.float64, copy=False), (pad_left, pad_right), mode="edge")
    kernel = np.ones(w, dtype=np.float64) / float(w)
    return np.convolve(xpad, kernel, mode="valid")


def detect_initial_silence(
    energies,
    *,
    window_seconds: float,
    threshold_multiplier: float = 1.5,
    initial_window_seconds: float = 60.0,
    smoothing_window_seconds: float = 30.0,
):
    """Detect initial silence using an energy threshold method.

    Returns:
      (silence_end_time_seconds | None, analysis_dict)

    If no clear transition is found, returns (None, analysis) and does not propose removal.
    """

    energies = np.asarray(energies, dtype=np.float64)
    n = len(energies)
    if n == 0:
        return None, {"reason": "empty_energies"}

    initial_frames = min(n, _seconds_to_frames(initial_window_seconds, window_seconds, minimum=1))
    initial_avg = float(np.mean(energies[:initial_frames]))

    threshold = float(initial_avg * float(threshold_multiplier))

    smoothing_frames = min(n, _seconds_to_frames(smoothing_window_seconds, window_seconds, minimum=1))
    smoothed = _moving_average_centered_same(energies, smoothing_frames)

    # Find earliest time where smoothed energy exceeds threshold.
    crossing_idx = None
    for i, val in enumerate(smoothed):
        if float(val) > threshold:
            crossing_idx = i
            break

    analysis = {
        "window_seconds": float(window_seconds),
        "initial_window_seconds": float(initial_window_seconds),
        "smoothing_window_seconds": float(smoothing_window_seconds),
        "initial_frames": int(initial_frames),
        "smoothing_frames": int(smoothing_frames),
        "initial_avg": float(initial_avg),
        "threshold": float(threshold),
    }

    if crossing_idx is None:
        analysis["reason"] = "no_threshold_crossing_found"
        return None, analysis

    silence_end_time = float(crossing_idx) * float(window_seconds)
    analysis["crossing_index"] = int(crossing_idx)
    analysis["silence_end_time_seconds"] = float(silence_end_time)

    # If the crossing is at t=0, we treat it as no initial silence removal.
    if silence_end_time <= 0:
        analysis["reason"] = "crossing_at_or_before_zero"
        return None, analysis

    return silence_end_time, analysis


def main():
    parser = argparse.ArgumentParser(description="Detect initial silence from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--threshold-multiplier", type=float, default=1.5, help="Threshold multiplier (default: 1.5)")
    parser.add_argument("--initial-window", type=float, default=60.0, help="Baseline window in seconds (default: 60)")
    parser.add_argument("--smoothing-window", type=float, default=30.0, help="Smoothing window in seconds (default: 30)")

    args = parser.parse_args()

    print(f"Detecting initial silence from: {args.energies}")
    print(
        "Parameters: "
        f"multiplier={args.threshold_multiplier}, "
        f"initial={args.initial_window}s, "
        f"smoothing={args.smoothing_window}s"
    )

    # Load energy data
    with open(args.energies) as f:
        energy_data = json.load(f)

    energies = energy_data.get("energies", [])
    window_seconds = float(energy_data.get("window_seconds", 1.0))
    total_seconds = float(energy_data.get("total_seconds", len(energies) * window_seconds))

    # Detect initial silence
    silence_end_time, analysis = detect_initial_silence(
        energies,
        window_seconds=window_seconds,
        threshold_multiplier=args.threshold_multiplier,
        initial_window_seconds=args.initial_window,
        smoothing_window_seconds=args.smoothing_window,
    )

    # Build segments list (half-open: [0, end))
    segments = []
    if silence_end_time is not None and silence_end_time > 0:
        end_t = min(float(silence_end_time), float(total_seconds))
        if end_t > 0:
            segments.append({"start": 0.0, "end": float(end_t), "duration": float(end_t)})

    total_removed = float(sum(s["duration"] for s in segments))

    # Save result
    result = {
        "method": "energy_threshold",
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": total_removed,
        "parameters": {
            "threshold_multiplier": args.threshold_multiplier,
            "initial_window_seconds": args.initial_window,
            "smoothing_window_seconds": args.smoothing_window,
        },
        "analysis": analysis,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    if segments:
        print(f"\nInitial silence detected: {segments[0]['duration']:.3f}s")
    else:
        print("\nInitial silence detected: 0s (no removal proposed)")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
