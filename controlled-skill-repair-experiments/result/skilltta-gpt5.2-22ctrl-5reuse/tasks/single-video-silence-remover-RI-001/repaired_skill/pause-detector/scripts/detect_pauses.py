#!/usr/bin/env python3
"""\
Pause detector - finds pauses using local dynamic threshold on energy data.

Correctness notes:
- Energies are computed over windows of length `window_seconds` (from energies.json).
- CLI time parameters (`--start-time`, `--min-duration`, `--window-size`) are interpreted
  as *seconds* and converted to energy-frame counts using `window_seconds`.
- Output segments are always emitted in seconds (numbers), regardless of energy window size.
"""

import argparse
import json

import numpy as np
from scipy.ndimage import uniform_filter1d


def _seconds_to_frames(seconds: float, window_seconds: float, *, how: str = "ceil") -> int:
    if window_seconds <= 0:
        raise ValueError("window_seconds must be > 0")
    seconds = max(0.0, float(seconds))
    x = seconds / window_seconds
    if how == "ceil":
        return int(np.ceil(x - 1e-12))
    if how == "floor":
        return int(np.floor(x + 1e-12))
    if how == "round":
        return int(np.round(x))
    raise ValueError("how must be one of: ceil, floor, round")


def _frames_to_seconds(frames: int, window_seconds: float) -> float:
    return float(frames) * float(window_seconds)


def _r3(x: float) -> float:
    return float(round(float(x), 3))


def detect_pauses(
    energies,
    *,
    window_seconds: float = 1.0,
    start_time: float = 0.0,
    threshold_ratio: float = 0.5,
    min_duration: float = 2.0,
    window_size: float = 30.0,
):
    """Detect pauses using a local dynamic threshold.

    All time-valued parameters are in seconds; internally converted to frame indices.
    Returns a list of segments with times in seconds.
    """

    energies = np.asarray(energies, dtype=np.float64)
    n = len(energies)
    if n == 0:
        return []

    # Convert seconds -> frames
    start_idx = max(0, min(n, _seconds_to_frames(start_time, window_seconds, how="floor")))
    min_frames = max(1, _seconds_to_frames(min_duration, window_seconds, how="ceil"))
    window_frames = max(1, _seconds_to_frames(window_size, window_seconds, how="round"))

    # Calculate local average using sliding window over frames
    local_avg = uniform_filter1d(energies, size=window_frames, mode="nearest")

    # Identify low-energy frames
    is_low_energy = energies < (local_avg * float(threshold_ratio))

    # Group continuous low-energy frames into segments starting from start_idx
    segments = []
    in_segment = False
    segment_start = 0

    for i in range(start_idx, n):
        if bool(is_low_energy[i]):
            if not in_segment:
                segment_start = i
                in_segment = True
        else:
            if in_segment:
                end_idx = i
                dur_frames = end_idx - segment_start
                if dur_frames >= min_frames:
                    start_s = _frames_to_seconds(segment_start, window_seconds)
                    end_s = _frames_to_seconds(end_idx, window_seconds)
                    segments.append({"start": _r3(start_s), "end": _r3(end_s), "duration": _r3(end_s - start_s)})
                in_segment = False

    # Handle trailing segment
    if in_segment:
        end_idx = n
        dur_frames = end_idx - segment_start
        if dur_frames >= min_frames:
            start_s = _frames_to_seconds(segment_start, window_seconds)
            end_s = _frames_to_seconds(end_idx, window_seconds)
            segments.append({"start": _r3(start_s), "end": _r3(end_s), "duration": _r3(end_s - start_s)})

    return segments


def main():
    parser = argparse.ArgumentParser(description="Detect pauses from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument(
        "--start-time",
        type=float,
        default=0.0,
        help="Start analyzing from this time in seconds (default: 0)",
    )
    parser.add_argument("--threshold-ratio", type=float, default=0.5, help="Threshold ratio (default: 0.5)")
    parser.add_argument(
        "--min-duration",
        type=float,
        default=2.0,
        help="Minimum pause duration in seconds (default: 2)",
    )
    parser.add_argument(
        "--window-size",
        type=float,
        default=30.0,
        help="Local average window size in seconds (default: 30)",
    )

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

    energies = energy_data["energies"]
    window_seconds = float(energy_data.get("window_seconds", 1.0))

    segments = detect_pauses(
        energies,
        window_seconds=window_seconds,
        start_time=args.start_time,
        threshold_ratio=args.threshold_ratio,
        min_duration=args.min_duration,
        window_size=args.window_size,
    )

    total_duration = float(sum(s["duration"] for s in segments))

    result = {
        "method": "local_dynamic_threshold",
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": _r3(total_duration),
        "parameters": {
            "threshold_ratio": args.threshold_ratio,
            "window_size": args.window_size,
            "min_duration": args.min_duration,
            "start_time": args.start_time,
        },
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nFound {len(segments)} pauses totaling {total_duration:.3f}s ({total_duration/60:.2f} min)")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
