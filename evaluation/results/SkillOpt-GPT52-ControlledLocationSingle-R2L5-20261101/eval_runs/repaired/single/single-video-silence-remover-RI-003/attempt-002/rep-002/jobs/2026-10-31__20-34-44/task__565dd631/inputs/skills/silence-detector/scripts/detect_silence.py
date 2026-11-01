#!/usr/bin/env python3
"""
Silence detector - finds initial silence segment using energy data.
Detects low-energy periods at the start of audio (e.g., title slides, setup time).
"""

import argparse
import json

import numpy as np


def detect_initial_silence(energies, threshold_multiplier=1.5, initial_window=60, smoothing_window=30):
    """Detect initial silence using energy threshold method."""

    energies = np.array(energies)

    # Calculate initial average (baseline from silent period)
    initial_avg = np.mean(energies[: min(initial_window, len(energies))])

    # Calculate threshold
    threshold = initial_avg * threshold_multiplier

    # Apply moving average to smooth
    alignment_offset = 0.0
    if len(energies) >= smoothing_window:
        smoothed = np.convolve(energies, np.ones(smoothing_window) / smoothing_window, mode="valid")
        # A value at index i summarizes [i, i + smoothing_window), so map the
        # threshold crossing to that window's temporal center.
        alignment_offset = (smoothing_window - 1) / 2
    else:
        smoothed = energies

    # Find where smoothed energy exceeds threshold (end of silence)
    silence_end = 0
    transition_index = None
    for i in range(len(smoothed)):
        if smoothed[i] > threshold:
            transition_index = i
            silence_end = min(len(energies), int(round(i + alignment_offset)))
            break

    return silence_end, {
        "initial_avg": float(initial_avg),
        "threshold": float(threshold),
        "smoothed_transition_index": transition_index,
        "timestamp_alignment_offset": alignment_offset,
    }


def main():
    parser = argparse.ArgumentParser(description="Detect initial silence from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--threshold-multiplier", type=float, default=1.5, help="Threshold multiplier applied to baseline energy (default: 1.5)")
    parser.add_argument("--initial-window", type=int, default=60, help="Initial window length in frames for baseline estimation (default: 60)")
    parser.add_argument("--smoothing-window", type=int, default=30, help="Moving-average smoothing window length in frames (default: 30)")
    parser.add_argument("--fps", type=float, default=None, help="Optional energy frame rate (frames/sec). If provided, outputs segment times in seconds; otherwise outputs frame indices.")

    args = parser.parse_args()

    print(f"Detecting initial silence from: {args.energies}")
    print(
        f"Parameters: multiplier={args.threshold_multiplier}, initial_window={args.initial_window} frames, "
        f"smoothing_window={args.smoothing_window} frames, fps={args.fps}"
    )

    # Load energy data
    with open(args.energies) as f:
        energy_data = json.load(f)

    energies = energy_data["energies"]
    total_seconds = energy_data["total_seconds"]



    # Determine output timebase.
    # Energies are typically per-frame values; if fps is known, map frame indices -> seconds.
    fps = args.fps if args.fps is not None else energy_data.get("fps")
    if fps is not None and fps <= 0:
        raise ValueError("fps must be > 0 when provided")
    # Detect initial silence
    silence_end, analysis = detect_initial_silence(energies, args.threshold_multiplier, args.initial_window, args.smoothing_window)

    # Build segments list.
    # If fps is available, emit seconds; otherwise emit frame indices.
    segments = []
    if silence_end > 0:
        if fps is not None:
            start_t = 0.0
            end_t = float(silence_end) / float(fps)
            segments.append({"start": start_t, "end": end_t, "duration": end_t - start_t})
        else:
            segments.append({"start": 0, "end": int(silence_end), "duration": int(silence_end)})

    # Save result
    total_removed = segments[0]["duration"] if segments else 0
    result = {
        "method": "energy_threshold",
        "timebase": "seconds" if fps is not None else "frames",
        "fps": fps,
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": float(total_removed) if fps is not None else None,
        "total_duration_frames": int(silence_end) if fps is None else None,
        "parameters": {
            "threshold_multiplier": args.threshold_multiplier,
            "initial_window_frames": args.initial_window,
            "smoothing_window_frames": args.smoothing_window,
        },
        "analysis": {
            **analysis,
            "silence_end_frame_aligned": int(silence_end),
        },
        "source": {
            "total_seconds": total_seconds,
            "energies_length": len(energies),
        },
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nInitial silence detected: {silence_end}s ({silence_end/60:.2f} min)")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
