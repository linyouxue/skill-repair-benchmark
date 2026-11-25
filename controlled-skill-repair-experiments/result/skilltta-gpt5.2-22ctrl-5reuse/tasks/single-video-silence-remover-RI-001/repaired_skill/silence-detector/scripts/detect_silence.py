#!/usr/bin/env python3
"""\
Silence detector - finds initial silence segment using energy data.
Detects low-energy periods at the start of audio (e.g., title slides, setup time).

Key correctness notes:
- Energies are computed over windows of length `window_seconds` (from energies.json).
- All CLI time parameters are interpreted as *seconds* and converted to energy-frame indices
  using `window_seconds`.
- Smoothing is implemented as a centered moving average with edge padding, producing a
  smoothed array of the same length as the original energies. Therefore energy index i maps
  1:1 to smoothed index i (no systematic convolution offset).
- If no threshold crossing is found, we conservatively return no removal segment.
"""

import argparse
import json

import numpy as np


def _seconds_to_frames(seconds: float, window_seconds: float, *, how: str = "ceil") -> int:
    """Convert seconds to a non-negative integer number of energy frames."""
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


def _smooth_centered_moving_average(x: np.ndarray, window_frames: int) -> np.ndarray:
    """Centered moving average with edge padding; output length equals input length."""
    x = np.asarray(x, dtype=np.float64)
    if window_frames <= 1 or len(x) == 0:
        return x

    w = int(window_frames)
    pad_left = w // 2
    pad_right = (w - 1) - pad_left

    # Edge padding avoids introducing artificial low-energy values at the boundaries.
    padded = np.pad(x, (pad_left, pad_right), mode="edge")
    kernel = np.ones(w, dtype=np.float64) / float(w)

    # 'valid' on the padded signal gives same-length output aligned to original indices.
    smoothed = np.convolve(padded, kernel, mode="valid")
    return smoothed


def detect_initial_silence(
    energies,
    *,
    window_seconds: float = 1.0,
    threshold_multiplier: float = 1.5,
    initial_window: float = 60.0,
    smoothing_window: float = 30.0,
):
    """Detect initial silence using an energy threshold method.

    Returns:
      (silence_end_seconds, analysis_dict)

    Where silence_end_seconds is the end time of the initial silence segment [0, end).
    If no reliable transition is found, silence_end_seconds is 0.0.
    """

    energies = np.asarray(energies, dtype=np.float64)
    n = len(energies)
    if n == 0:
        return 0.0, {
            "found_transition": False,
            "reason": "empty_energies",
            "initial_avg": None,
            "threshold": None,
            "window_seconds": float(window_seconds),
        }

    # Convert seconds-based parameters to frame counts.
    initial_frames = max(1, min(n, _seconds_to_frames(initial_window, window_seconds, how="ceil")))
    smoothing_frames = max(1, _seconds_to_frames(smoothing_window, window_seconds, how="ceil"))

    # Baseline: mean energy over the initial window.
    initial_avg = float(np.mean(energies[:initial_frames]))
    threshold = float(initial_avg * float(threshold_multiplier))

    smoothed = _smooth_centered_moving_average(energies, smoothing_frames)

    found = False
    silence_end_idx = 0
    for i, val in enumerate(smoothed):
        if val > threshold:
            silence_end_idx = int(i)
            found = True
            break

    # Conservative behavior: if we cannot find a clear transition, remove nothing.
    if not found:
        return 0.0, {
            "found_transition": False,
            "reason": "no_threshold_crossing",
            "initial_avg": initial_avg,
            "threshold": threshold,
            "window_seconds": float(window_seconds),
            "initial_window_seconds": float(initial_window),
            "smoothing_window_seconds": float(smoothing_window),
            "initial_frames": int(initial_frames),
            "smoothing_frames": int(smoothing_frames),
        }

    silence_end_seconds = _frames_to_seconds(silence_end_idx, window_seconds)

    return float(silence_end_seconds), {
        "found_transition": True,
        "initial_avg": initial_avg,
        "threshold": threshold,
        "silence_end_index": int(silence_end_idx),
        "silence_end_seconds": float(silence_end_seconds),
        "window_seconds": float(window_seconds),
        "initial_window_seconds": float(initial_window),
        "smoothing_window_seconds": float(smoothing_window),
        "initial_frames": int(initial_frames),
        "smoothing_frames": int(smoothing_frames),
    }


def _r3(x: float) -> float:
    return float(round(float(x), 3))


def main():
    parser = argparse.ArgumentParser(description="Detect initial silence from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument(
        "--threshold-multiplier",
        type=float,
        default=1.5,
        help="Threshold multiplier (default: 1.5)",
    )
    parser.add_argument(
        "--initial-window",
        type=float,
        default=60,
        help="Initial window for baseline in seconds (default: 60)",
    )
    parser.add_argument(
        "--smoothing-window",
        type=float,
        default=30,
        help="Smoothing window in seconds (default: 30)",
    )

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

    energies = energy_data["energies"]
    window_seconds = float(energy_data.get("window_seconds", 1.0))

    silence_end_seconds, analysis = detect_initial_silence(
        energies,
        window_seconds=window_seconds,
        threshold_multiplier=args.threshold_multiplier,
        initial_window=args.initial_window,
        smoothing_window=args.smoothing_window,
    )

    # Build segments list (same schema as pause detector)
    segments = []
    if silence_end_seconds > 0:
        end = _r3(silence_end_seconds)
        segments.append({"start": 0.0, "end": end, "duration": _r3(end - 0.0)})

    total_removed = float(sum(s["duration"] for s in segments))

    result = {
        "method": "energy_threshold",
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": _r3(total_removed),
        "parameters": {
            "threshold_multiplier": args.threshold_multiplier,
            "initial_window": args.initial_window,
            "smoothing_window": args.smoothing_window,
        },
        "analysis": analysis,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nInitial silence detected: {silence_end_seconds:.3f}s ({silence_end_seconds/60:.2f} min)")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
