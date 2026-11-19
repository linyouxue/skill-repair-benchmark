#!/usr/bin/env python3
"""silence-detector

Detect an initial low-content segment ("opening") from pre-computed RMS energy.

This detector is intended for removing non-teaching pre-roll such as:
- Title cards / static opening frames
- Long initial silence / setup time

It is intentionally lightweight (stdlib-only) and robust:
- Uses a robust baseline from the early part of the audio (median / percentile).
- Uses a *centered* moving average so the returned cut time is aligned.
- Optionally requires the signal to be above threshold for a sustained duration
  to avoid cutting on short spikes.

Input: energies JSON from `energy-calculator`.
Output: JSON with `segments` list of {start,end,duration} in seconds.
"""

from __future__ import annotations

import argparse
import json
import math
from typing import Any, Dict, List, Tuple


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(float(v) for v in values)
    if p <= 0:
        return float(xs[0])
    if p >= 100:
        return float(xs[-1])
    k = (len(xs) - 1) * (float(p) / 100.0)
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return float(xs[f])
    d = k - f
    return float(xs[f] * (1.0 - d) + xs[c] * d)


def _moving_average_centered_nearest(values: List[float], window: int) -> List[float]:
    """Centered moving average with nearest edge padding."""
    n = len(values)
    if n == 0:
        return []
    window = max(1, int(window))
    half = window // 2

    def clamp_index(i: int) -> int:
        return 0 if i < 0 else (n - 1 if i >= n else i)

    out: List[float] = []
    for i in range(n):
        s = 0.0
        for j in range(i - half, i - half + window):
            s += float(values[clamp_index(j)])
        out.append(s / window)
    return out


def detect_initial_silence_seconds(
    energies: List[float],
    *,
    window_seconds: float,
    search_max_seconds: float = 120.0,
    baseline_seconds: float = 30.0,
    smoothing_seconds: float = 3.0,
    threshold_multiplier: float = 2.0,
    baseline_percentile: float = 50.0,
    sustain_seconds: float = 2.0,
    min_opening_seconds: float = 0.0,
    max_opening_seconds: float = 180.0,
) -> Tuple[float, Dict[str, float]]:
    """Return opening_end_seconds and analysis metadata."""

    if window_seconds <= 0:
        raise ValueError("window_seconds must be > 0")
    if threshold_multiplier <= 0:
        raise ValueError("threshold_multiplier must be > 0")

    n = len(energies)
    if n == 0:
        return 0.0, {}

    # Convert seconds -> windows
    search_max_w = max(1, int(round(float(search_max_seconds) / float(window_seconds))))
    baseline_w = max(1, int(round(float(baseline_seconds) / float(window_seconds))))
    smooth_w = max(1, int(round(float(smoothing_seconds) / float(window_seconds))))
    sustain_w = max(1, int(round(float(sustain_seconds) / float(window_seconds))))

    search_n = min(n, search_max_w)
    baseline_slice = [float(v) for v in energies[: min(n, baseline_w)]]

    baseline = _percentile(baseline_slice, baseline_percentile)
    threshold = baseline * float(threshold_multiplier)

    smoothed = _moving_average_centered_nearest([float(v) for v in energies], smooth_w)

    opening_end_idx = 0
    run = 0
    for i in range(search_n):
        if float(smoothed[i]) > threshold:
            run += 1
            if run >= sustain_w:
                # Conservative: cut at the *start* of the sustained run.
                opening_end_idx = i - sustain_w + 1
                break
        else:
            run = 0

    opening_end_seconds = opening_end_idx * float(window_seconds)

    # Clip to configured bounds
    opening_end_seconds = max(float(min_opening_seconds), opening_end_seconds)
    opening_end_seconds = min(float(max_opening_seconds), opening_end_seconds)

    return float(opening_end_seconds), {
        "window_seconds": float(window_seconds),
        "baseline_percentile": float(baseline_percentile),
        "baseline": float(baseline),
        "threshold_multiplier": float(threshold_multiplier),
        "threshold": float(threshold),
        "baseline_seconds": float(baseline_seconds),
        "smoothing_seconds": float(smoothing_seconds),
        "sustain_seconds": float(sustain_seconds),
        "search_max_seconds": float(search_max_seconds),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect initial silence/opening from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")

    parser.add_argument("--search-max", type=float, default=120.0, help="Search at most this many seconds (default: 120)")
    parser.add_argument("--baseline-seconds", type=float, default=30.0, help="Seconds for baseline estimate (default: 30)")
    parser.add_argument("--smoothing-seconds", type=float, default=3.0, help="Smoothing window in seconds (default: 3)")
    parser.add_argument(
        "--threshold-multiplier",
        type=float,
        default=2.0,
        help="Threshold multiplier over baseline (default: 2.0)",
    )
    parser.add_argument(
        "--baseline-percentile",
        type=float,
        default=50.0,
        help="Percentile for baseline (default: 50, median)",
    )
    parser.add_argument(
        "--sustain-seconds",
        type=float,
        default=2.0,
        help="Require energy above threshold for this long (default: 2.0)",
    )
    parser.add_argument(
        "--min-opening",
        type=float,
        default=0.0,
        help="Minimum opening length in seconds (default: 0)",
    )
    parser.add_argument(
        "--max-opening",
        type=float,
        default=180.0,
        help="Maximum opening length in seconds (default: 180)",
    )
    parser.add_argument(
        "--round-ndigits",
        type=int,
        default=3,
        help="Round output start/end/duration to this many decimals (default: 3)",
    )

    args = parser.parse_args()

    print(f"Detecting opening from: {args.energies}")

    with open(args.energies, encoding="utf-8") as f:
        energy_data: Dict[str, Any] = json.load(f)

    energies = [float(v) for v in energy_data.get("energies", [])]
    window_seconds = float(energy_data.get("window_seconds", 1.0))

    opening_end, analysis = detect_initial_silence_seconds(
        energies,
        window_seconds=window_seconds,
        search_max_seconds=args.search_max,
        baseline_seconds=args.baseline_seconds,
        smoothing_seconds=args.smoothing_seconds,
        threshold_multiplier=args.threshold_multiplier,
        baseline_percentile=args.baseline_percentile,
        sustain_seconds=args.sustain_seconds,
        min_opening_seconds=args.min_opening,
        max_opening_seconds=args.max_opening,
    )

    nd = int(args.round_ndigits)

    segments: List[Dict[str, float]] = []
    if opening_end > 0:
        segments.append({"start": 0.0, "end": opening_end, "duration": opening_end})

    result = {
        "method": "energy_opening_threshold_sustained",
        "segments": [{"start": round(s["start"], nd), "end": round(s["end"], nd), "duration": round(s["duration"], nd)} for s in segments],
        "total_segments": len(segments),
        "total_duration_seconds": round(opening_end, nd) if opening_end > 0 else 0.0,
        "parameters": {
            "search_max_seconds": args.search_max,
            "baseline_seconds": args.baseline_seconds,
            "smoothing_seconds": args.smoothing_seconds,
            "threshold_multiplier": args.threshold_multiplier,
            "baseline_percentile": args.baseline_percentile,
            "sustain_seconds": args.sustain_seconds,
            "min_opening_seconds": args.min_opening,
            "max_opening_seconds": args.max_opening,
            "round_ndigits": nd,
        },
        "analysis": {k: round(float(v), nd) for k, v in analysis.items()},
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nOpening detected: {result['total_duration_seconds']}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
