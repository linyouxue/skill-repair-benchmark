#!/usr/bin/env python3
"""
Silence detector - finds the initial opening / pre-roll segment in a track
using pre-computed per-second energies.

The opening may be noticeably LOUDER than the following content (static
frames with intro music / hum) or noticeably QUIETER (true pre-roll
silence). To handle both patterns from one entry point, the detector looks
for the first *local step* in smoothed energy inside the allowed opening
region: the first second ``t`` where the median of a short window just
before ``t`` differs from the median of a short window just after ``t`` by
at least ``min_change_ratio``, and where the new regime is sustained for
``sustain_seconds`` afterwards.

A conservative ``max_opening_fraction`` cap keeps the detector from
swallowing real teaching content when the energy profile is ambiguous, and
the "first qualifying step" rule keeps a later, bigger swing from pulling
the boundary past the true opening-to-content transition.

The detector reports only the opening-to-content transition. Any quiet
setup period immediately after the opening is left to the pause-detector,
which can then describe it with the correct granularity instead of
collapsing it into one over-long opening segment.
"""

import argparse
import json

import numpy as np


def _smooth(energies, smooth_window):
    sw = max(1, int(smooth_window))
    if len(energies) >= sw:
        kernel = np.ones(sw) / sw
        return np.convolve(energies, kernel, mode="same")
    return energies.copy()


def _confirm_sustained_after(smoothed, t, after_median, before_median, sustain_seconds):
    """Check the boundary is followed by sustained content-side behaviour.

    Most of the first ``sustain_seconds`` seconds after ``t`` must be
    closer (in log-energy) to ``after_median`` than to ``before_median``,
    which rejects boundaries caused by a single transient dip or spike.
    """
    sustain = max(1, int(sustain_seconds))
    end = min(len(smoothed), t + sustain)
    if end - t < max(3, sustain // 2):
        return False
    window = smoothed[t:end]
    eps = 1e-6
    log_w = np.log(np.maximum(window, eps))
    log_before = np.log(max(before_median, eps))
    log_after = np.log(max(after_median, eps))
    closer_to_after = np.abs(log_w - log_after) < np.abs(log_w - log_before)
    return float(np.mean(closer_to_after)) >= 0.6


def detect_initial_silence(
    energies,
    smoothing_window=5,
    min_opening=1,
    max_opening_fraction=0.3,
    min_change_ratio=0.35,
    local_window=20,
    sustain_seconds=10,
    search_step=1,
):
    """Detect the end of the opening via the first local step.

    Returns (silence_end_seconds, analysis_dict). ``silence_end_seconds == 0``
    means no clear opening was identified.
    """

    energies = np.asarray(energies, dtype=float)
    n = len(energies)
    if n == 0:
        return 0, {"note": "empty input", "track_length_seconds": 0}

    smoothed = _smooth(energies, smoothing_window)

    max_opening = max(int(min_opening) + 1, int(n * max_opening_fraction))
    max_opening = min(max_opening, n - max(5, int(local_window) // 3))
    if max_opening <= int(min_opening):
        return 0, {
            "note": "track too short for opening search",
            "track_length_seconds": int(n),
        }

    track_median = float(np.median(smoothed))

    lw = max(5, int(local_window))
    step = max(1, int(search_step))

    best_t = 0
    best_score = 0.0
    best_before = best_after = 0.0

    # Walk forward; pick the first candidate that clears min_change_ratio
    # and whose change is confirmed as sustained. Among confirmed candidates
    # we tie-break on magnitude only within a brief refinement window to
    # snap to the sharp edge instead of a nearby weaker step.
    first_hit = None
    refine_t = None
    refine_score = 0.0
    refine_before = refine_after = 0.0
    REFINE_SPAN = max(5, lw // 2)

    for t in range(max(int(min_opening), 1), max_opening + 1, step):
        a = max(0, t - lw)
        b = min(len(smoothed), t + lw)
        if t - a < 3 or b - t < 3:
            continue
        before = smoothed[a:t]
        after = smoothed[t:b]
        before_med = float(np.median(before))
        after_med = float(np.median(after))
        denom = max(before_med, after_med)
        if denom <= 0:
            continue
        change_ratio = abs(before_med - after_med) / denom
        if change_ratio > best_score:
            best_score = change_ratio
            best_t = t
            best_before = before_med
            best_after = after_med
        if change_ratio >= min_change_ratio:
            if _confirm_sustained_after(smoothed, t, after_med, before_med, sustain_seconds):
                if first_hit is None:
                    first_hit = t
                    refine_t = t
                    refine_score = change_ratio
                    refine_before = before_med
                    refine_after = after_med
                elif t - first_hit <= REFINE_SPAN and change_ratio > refine_score:
                    refine_t = t
                    refine_score = change_ratio
                    refine_before = before_med
                    refine_after = after_med
                elif t - first_hit > REFINE_SPAN:
                    break

    analysis = {
        "track_length_seconds": int(n),
        "track_median": track_median,
        "best_boundary_seconds": int(best_t),
        "best_change_ratio": float(best_score),
        "before_median": float(best_before),
        "after_median": float(best_after),
        "max_opening_seconds": int(max_opening),
        "min_change_ratio": float(min_change_ratio),
        "local_window": int(lw),
    }

    if refine_t is None:
        return 0, {**analysis, "note": "no qualifying local step"}

    analysis.update(
        {
            "best_boundary_seconds": int(refine_t),
            "best_change_ratio": float(refine_score),
            "before_median": float(refine_before),
            "after_median": float(refine_after),
        }
    )
    return int(refine_t), analysis


def main():
    parser = argparse.ArgumentParser(description="Detect initial opening via a local energy step")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--smoothing-window", type=int, default=5, help="Smoothing window in seconds (default: 5)")
    parser.add_argument("--min-opening", type=int, default=1, help="Minimum opening length to consider in seconds (default: 1)")
    parser.add_argument("--max-opening-fraction", type=float, default=0.3, help="Hard cap on opening as fraction of total track (default: 0.3)")
    parser.add_argument("--min-change-ratio", type=float, default=0.35, help="Minimum relative change between local before/after medians required to accept the boundary (default: 0.35)")
    parser.add_argument("--local-window", type=int, default=20, help="Seconds used on each side of a candidate boundary for the local median comparison (default: 20)")
    parser.add_argument("--sustain-seconds", type=int, default=10, help="Seconds of post-boundary data that must track the new median (default: 10)")

    args = parser.parse_args()

    print(f"Detecting opening from: {args.energies}")
    print(
        f"Parameters: smoothing={args.smoothing_window}s, "
        f"min_opening={args.min_opening}s, max_opening_fraction={args.max_opening_fraction}, "
        f"min_change_ratio={args.min_change_ratio}, local_window={args.local_window}s, "
        f"sustain={args.sustain_seconds}s"
    )

    with open(args.energies) as f:
        energy_data = json.load(f)

    energies = energy_data["energies"]

    silence_end, analysis = detect_initial_silence(
        energies,
        smoothing_window=args.smoothing_window,
        min_opening=args.min_opening,
        max_opening_fraction=args.max_opening_fraction,
        min_change_ratio=args.min_change_ratio,
        local_window=args.local_window,
        sustain_seconds=args.sustain_seconds,
    )

    segments = []
    if silence_end > 0:
        segments.append({"start": 0, "end": int(silence_end), "duration": int(silence_end)})

    result = {
        "method": "energy_local_step",
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": int(silence_end) if silence_end > 0 else 0,
        "parameters": {
            "smoothing_window": args.smoothing_window,
            "min_opening": args.min_opening,
            "max_opening_fraction": args.max_opening_fraction,
            "min_change_ratio": args.min_change_ratio,
            "local_window": args.local_window,
            "sustain_seconds": args.sustain_seconds,
        },
        "analysis": analysis,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    if silence_end > 0:
        print(f"\nOpening detected: 0..{silence_end}s ({silence_end/60:.2f} min)")
    else:
        print("\nNo clear opening detected.")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
