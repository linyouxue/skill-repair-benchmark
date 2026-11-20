#!/usr/bin/env python3
"""
Pause detector - finds pauses inside audio from pre-computed per-second
energy data.

A second counts as "quiet" when either
  (a) its energy is below a fraction of a local moving-average energy, OR
  (b) its energy is below an absolute low-energy floor derived from a low
      quantile of the whole track.

Consecutive quiet seconds are grouped into pauses. ``--merge-gap`` lets two
quiet runs separated by a brief burst of activity merge into a single pause,
which is useful when natural speech produces short consonant transients that
would otherwise split a real pause into fragments.
"""

import argparse
import json

import numpy as np
from scipy.ndimage import uniform_filter1d


def detect_pauses(
    energies,
    start_time=0,
    end_time=None,
    threshold_ratio=0.5,
    min_duration=2,
    window_size=30,
    absolute_quantile=0.15,
    absolute_margin=1.1,
    merge_gap=5,
):
    """Detect pauses using a local dynamic threshold plus an absolute floor.

    Parameters
    ----------
    energies : list or array of per-second RMS energies.
    start_time : skip seconds before this index (inclusive).
    end_time : optional exclusive end; defaults to len(energies).
    threshold_ratio : local-average multiplier for the relative threshold.
    min_duration : minimum pause length to report (seconds).
    window_size : local-average window size (seconds).
    absolute_quantile : quantile of the whole-track energy used to form the
        absolute silence floor.
    absolute_margin : the floor is set to quantile * absolute_margin.
    merge_gap : seconds; two quiet runs separated by this many or fewer
        active seconds are merged into one pause.
    """

    energies = np.asarray(energies, dtype=float)
    n = len(energies)
    if n == 0:
        return []

    if end_time is None or end_time > n:
        end_time = n
    start_time = max(0, int(start_time))
    end_time = int(end_time)
    if start_time >= end_time:
        return []

    local_avg = uniform_filter1d(energies, size=max(1, int(window_size)), mode="nearest")
    local_low = energies < (local_avg * threshold_ratio)

    try:
        q = max(0.0, min(1.0, absolute_quantile))
        floor = float(np.quantile(energies, q))
    except Exception:
        floor = float(np.min(energies))
    abs_low = energies < (floor * absolute_margin)

    is_quiet = local_low | abs_low

    segments = []
    in_segment = False
    segment_start = 0
    gap_run = 0

    for i in range(start_time, end_time):
        if is_quiet[i]:
            if not in_segment:
                segment_start = i
                in_segment = True
            gap_run = 0
        else:
            if in_segment:
                gap_run += 1
                if gap_run > merge_gap:
                    end_idx = i - gap_run + 1
                    duration = end_idx - segment_start
                    if duration >= min_duration:
                        segments.append({"start": int(segment_start), "end": int(end_idx), "duration": int(duration)})
                    in_segment = False
                    gap_run = 0

    if in_segment:
        end_idx = end_time - gap_run
        duration = end_idx - segment_start
        if duration >= min_duration:
            segments.append({"start": int(segment_start), "end": int(end_idx), "duration": int(duration)})

    return segments


def main():
    parser = argparse.ArgumentParser(description="Detect pauses from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--start-time", type=int, default=0, help="Start time in seconds (default: 0)")
    parser.add_argument("--end-time", type=int, default=None, help="End time in seconds (default: end of track)")
    parser.add_argument("--threshold-ratio", type=float, default=0.5, help="Local threshold ratio (default: 0.5)")
    parser.add_argument("--min-duration", type=int, default=2, help="Minimum pause duration (default: 2)")
    parser.add_argument("--window-size", type=int, default=30, help="Local-average window size (default: 30)")
    parser.add_argument("--absolute-quantile", type=float, default=0.15, help="Whole-track quantile used for the absolute silence floor (default: 0.15)")
    parser.add_argument("--absolute-margin", type=float, default=1.1, help="Multiplier applied to the quantile floor (default: 1.1)")
    parser.add_argument("--merge-gap", type=int, default=5, help="Bridge up to this many active seconds between quiet runs (default: 5)")

    args = parser.parse_args()

    print(f"Detecting pauses from: {args.energies}")
    print(
        f"Parameters: start={args.start_time}s, end={args.end_time}, "
        f"ratio={args.threshold_ratio}, min={args.min_duration}s, window={args.window_size}s, "
        f"abs_quantile={args.absolute_quantile}, abs_margin={args.absolute_margin}, "
        f"merge_gap={args.merge_gap}s"
    )

    with open(args.energies) as f:
        energy_data = json.load(f)

    energies = energy_data["energies"]

    segments = detect_pauses(
        energies,
        start_time=args.start_time,
        end_time=args.end_time,
        threshold_ratio=args.threshold_ratio,
        min_duration=args.min_duration,
        window_size=args.window_size,
        absolute_quantile=args.absolute_quantile,
        absolute_margin=args.absolute_margin,
        merge_gap=args.merge_gap,
    )

    total_duration = sum(s["duration"] for s in segments)

    result = {
        "method": "local_dynamic_threshold_with_floor",
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": total_duration,
        "parameters": {
            "threshold_ratio": args.threshold_ratio,
            "window_size": args.window_size,
            "min_duration": args.min_duration,
            "start_time": args.start_time,
            "end_time": args.end_time,
            "absolute_quantile": args.absolute_quantile,
            "absolute_margin": args.absolute_margin,
            "merge_gap": args.merge_gap,
        },
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nFound {len(segments)} pauses totaling {total_duration}s ({total_duration/60:.2f} min)")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
