#!/usr/bin/env python3
"""
Pause detector - finds pauses using local dynamic threshold on energy data.

Contract:
- All times are in seconds (float).
- Segments are half-open intervals: [start, end)
- duration = end - start

This detector converts time parameters (seconds) into energy-frame indices using
energy-calculator's window_seconds.
"""

import argparse
import json
import math

import numpy as np
from scipy.ndimage import uniform_filter1d


def _sec_to_idx_floor(t_sec: float, window_seconds: float) -> int:
    if window_seconds <= 0:
        raise ValueError("window_seconds must be > 0")
    return int(math.floor(float(t_sec) / float(window_seconds) + 1e-12))


def detect_pauses(
    energies,
    *,
    window_seconds: float,
    start_time_seconds: float = 0.0,
    threshold_ratio: float = 0.5,
    min_duration_seconds: float = 2.0,
    window_size_seconds: float = 30.0,
):
    """Detect pauses using local dynamic threshold.

    A frame is considered low-energy if:
      energy[i] < local_avg[i] * threshold_ratio

    Note on tuning:
      - Larger threshold_ratio => easier to satisfy the inequality => more aggressive.
      - Smaller threshold_ratio => more conservative.
    """

    if window_seconds <= 0:
        raise ValueError("window_seconds must be > 0")
    if threshold_ratio <= 0:
        raise ValueError("threshold_ratio must be > 0")
    if min_duration_seconds < 0:
        raise ValueError("min_duration_seconds must be >= 0")

    energies = np.asarray(energies, dtype=np.float64)
    n = len(energies)
    if n == 0:
        return []

    window_frames = max(1, int(round(float(window_size_seconds) / float(window_seconds))))

    # Calculate local average using sliding window (aligned to input indices)
    local_avg = uniform_filter1d(energies, size=window_frames, mode="nearest")

    # Identify low-energy frames
    is_low_energy = energies < (local_avg * float(threshold_ratio))

    start_idx = max(0, _sec_to_idx_floor(start_time_seconds, window_seconds))

    segments = []
    in_segment = False
    seg_start_idx = 0

    for i in range(start_idx, n):
        if bool(is_low_energy[i]):
            if not in_segment:
                seg_start_idx = i
                in_segment = True
        else:
            if in_segment:
                seg_end_idx = i
                dur_sec = (seg_end_idx - seg_start_idx) * float(window_seconds)
                if dur_sec + 1e-9 >= float(min_duration_seconds):
                    start_t = seg_start_idx * float(window_seconds)
                    end_t = seg_end_idx * float(window_seconds)
                    segments.append({"start": float(start_t), "end": float(end_t), "duration": float(end_t - start_t)})
                in_segment = False

    # Handle last segment
    if in_segment:
        seg_end_idx = n
        dur_sec = (seg_end_idx - seg_start_idx) * float(window_seconds)
        if dur_sec + 1e-9 >= float(min_duration_seconds):
            start_t = seg_start_idx * float(window_seconds)
            end_t = seg_end_idx * float(window_seconds)
            segments.append({"start": float(start_t), "end": float(end_t), "duration": float(end_t - start_t)})

    return segments


def main():
    parser = argparse.ArgumentParser(description="Detect pauses from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--start-time", type=float, default=0.0, help="Start time in seconds (default: 0)")
    parser.add_argument("--threshold-ratio", type=float, default=0.5, help="Threshold ratio (default: 0.5)")
    parser.add_argument("--min-duration", type=float, default=2.0, help="Minimum pause duration in seconds (default: 2)")
    parser.add_argument("--window-size", type=float, default=30.0, help="Window size for local average in seconds (default: 30)")

    args = parser.parse_args()

    print(f"Detecting pauses from: {args.energies}")
    print(
        "Parameters: "
        f"start={args.start_time}s, "
        f"ratio={args.threshold_ratio}, "
        f"min={args.min_duration}s, "
        f"window={args.window_size}s"
    )

    # Load energy data
    with open(args.energies) as f:
        energy_data = json.load(f)

    energies = energy_data.get("energies", [])
    window_seconds = float(energy_data.get("window_seconds", 1.0))

    # Detect pauses
    segments = detect_pauses(
        energies,
        window_seconds=window_seconds,
        start_time_seconds=args.start_time,
        threshold_ratio=args.threshold_ratio,
        min_duration_seconds=args.min_duration,
        window_size_seconds=args.window_size,
    )

    total_duration = float(sum(s["duration"] for s in segments))

    # Save result
    result = {
        "method": "local_dynamic_threshold",
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": total_duration,
        "parameters": {
            "threshold_ratio": args.threshold_ratio,
            "window_size_seconds": args.window_size,
            "min_duration_seconds": args.min_duration,
            "start_time_seconds": args.start_time,
        },
        "analysis": {
            "window_seconds": window_seconds,
            "window_frames": max(1, int(round(float(args.window_size) / float(window_seconds)))) if window_seconds > 0 else None,
        },
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nFound {len(segments)} pauses totaling {total_duration:.3f}s ({total_duration/60:.2f} min)")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
