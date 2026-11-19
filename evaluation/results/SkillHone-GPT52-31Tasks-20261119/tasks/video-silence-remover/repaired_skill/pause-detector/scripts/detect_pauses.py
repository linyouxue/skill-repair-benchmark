#!/usr/bin/env python3
"""pause-detector

Detect pause/silence segments from pre-computed windowed RMS energy values.

Why energy-based detection:
- Avoids dependency on ffmpeg log parsing.
- Works reliably when energy windows are ~0.5–1.0s.

Key improvements over the original simple local-threshold method:
- Converts indices to seconds using `window_seconds` from the energy file.
- Uses a robust local baseline (moving median) instead of mean.
- Adds an absolute noise-floor gate so quiet speech is less likely to be removed.

Input is an energies JSON produced by the `energy-calculator` skill.
Output is a JSON with a `segments` list of {start,end,duration} in seconds.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from typing import Any, Dict, List, Tuple


def _percentile(values: List[float], p: float) -> float:
    """Compute percentile with linear interpolation."""
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


def _moving_average_centered_nearest(values: List[float], window_size: int) -> List[float]:
    """Centered moving average with nearest edge padding.

    Used to smooth out single-window spikes that can fragment pauses.
    """

    n = len(values)
    if n == 0:
        return []

    window_size = max(1, int(window_size))
    half = window_size // 2

    def clamp_index(i: int) -> int:
        return 0 if i < 0 else (n - 1 if i >= n else i)

    out: List[float] = []
    for i in range(n):
        s = 0.0
        for j in range(i - half, i - half + window_size):
            s += float(values[clamp_index(j)])
        out.append(s / float(window_size))
    return out


def _moving_median_nearest(values: List[float], window_size: int) -> List[float]:
    """Moving median with nearest edge padding."""
    n = len(values)
    if n == 0:
        return []

    window_size = max(1, int(window_size))
    half = window_size // 2

    def clamp_index(i: int) -> int:
        return 0 if i < 0 else (n - 1 if i >= n else i)

    out: List[float] = []
    for i in range(n):
        w = [float(values[clamp_index(j)]) for j in range(i - half, i - half + window_size)]
        out.append(float(statistics.median(w)))
    return out


def detect_pauses_seconds(
    energies: List[float],
    *,
    window_seconds: float,
    start_time_seconds: float = 0.0,
    min_duration_seconds: float = 2.0,
    window_size_seconds: float = 30.0,
    threshold_ratio: float = 0.5,
    noise_floor_percentile: float = 10.0,
    noise_floor_multiplier: float = 1.8,
    global_cap_ratio: float = 0.5,
    merge_gap_seconds: float = 0.0,
    smoothing_seconds: float = 1.0,
    allow_local_only: bool = True,
) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    """Return pause segments in seconds plus analysis metadata."""

    if window_seconds <= 0:
        raise ValueError("window_seconds must be > 0")
    if threshold_ratio <= 0:
        raise ValueError("threshold_ratio must be > 0")
    if min_duration_seconds < 0:
        raise ValueError("min_duration_seconds must be >= 0")
    if window_size_seconds <= 0:
        raise ValueError("window_size_seconds must be > 0")

    n = len(energies)
    if n == 0:
        return [], {}

    start_idx = max(0, int(math.floor(float(start_time_seconds) / float(window_seconds))))

    # Optional light smoothing of the raw energies before thresholding. This reduces
    # fragmentation when brief transients occur inside a pause.
    smooth_w = max(1, int(round(float(smoothing_seconds) / float(window_seconds))))
    energies_smoothed = _moving_average_centered_nearest([float(v) for v in energies], smooth_w)

    # Analyze only the region after `start_time_seconds` (e.g., after an opening).
    analysis_slice = [float(v) for v in energies_smoothed[start_idx:]] if start_idx < n else []
    if not analysis_slice:
        return [], {}

    local_window = max(1, int(round(float(window_size_seconds) / float(window_seconds))))
    local_median = _moving_median_nearest(analysis_slice, local_window)

    noise_floor = _percentile(analysis_slice, noise_floor_percentile)
    global_median = float(statistics.median(analysis_slice))

    # Absolute silence-ish threshold. Cap it relative to typical energy so we don't
    # accidentally classify quiet speech as silence.
    abs_threshold = min(noise_floor * float(noise_floor_multiplier), global_median * float(global_cap_ratio))

    # Build silence mask.
    #
    # Prefer a robust local baseline test. If the absolute noise-floor estimate is
    # too conservative (e.g., loud background hum), `allow_local_only` permits
    # pauses to be detected using the local test alone.
    # Silence mask is computed on the analyzed slice and then offset back to the
    # original timeline.
    silent_slice: List[bool] = [False] * len(analysis_slice)
    allow_local_only = bool(allow_local_only)
    for j in range(len(analysis_slice)):
        local_thr = float(local_median[j]) * float(threshold_ratio)
        below_local = float(analysis_slice[j]) < local_thr
        below_abs = float(analysis_slice[j]) < abs_threshold

        # Default behavior prefers recall: allow either gate to mark a window as
        # silent, while still biasing toward low-energy regions.
        silent_slice[j] = (below_local or below_abs) if allow_local_only else (below_local and below_abs)

    # Group into segments (in slice indices)
    segments_idx: List[Tuple[int, int]] = []
    in_seg = False
    seg_start = 0
    for j in range(len(silent_slice)):
        if silent_slice[j]:
            if not in_seg:
                seg_start = j
                in_seg = True
        else:
            if in_seg:
                segments_idx.append((seg_start, j))
                in_seg = False
    if in_seg:
        segments_idx.append((seg_start, len(silent_slice)))

    # Convert to seconds and filter by duration
    segs: List[Tuple[float, float]] = []
    for s_i, e_i in segments_idx:
        # Offset slice indices back to absolute indices
        s = (start_idx + s_i) * float(window_seconds)
        e = (start_idx + e_i) * float(window_seconds)
        if e > s and (e - s) >= float(min_duration_seconds) - 1e-9:
            segs.append((s, e))

    # Optional merge of close segments
    merge_gap_seconds = max(0.0, float(merge_gap_seconds))
    merged: List[Tuple[float, float]] = []
    for s, e in sorted(segs):
        if not merged:
            merged.append((s, e))
            continue
        ps, pe = merged[-1]
        if s <= pe + merge_gap_seconds:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))

    out: List[Dict[str, float]] = []
    for s, e in merged:
        out.append({"start": s, "end": e, "duration": e - s})

    analysis = {
        "window_seconds": float(window_seconds),
        "start_time_seconds": float(start_time_seconds),
        "threshold_ratio": float(threshold_ratio),
        "noise_floor_percentile": float(noise_floor_percentile),
        "noise_floor_multiplier": float(noise_floor_multiplier),
        "global_cap_ratio": float(global_cap_ratio),
        "abs_threshold": float(abs_threshold),
        "noise_floor": float(noise_floor),
        "global_median": float(global_median),
        "local_window_windows": float(local_window),
        "smoothing_seconds": float(smoothing_seconds),
        "use_or_gate": 1.0 if allow_local_only else 0.0,
    }

    return out, analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect pauses from energy data")
    parser.add_argument("--energies", required=True, help="Path to energy JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--start-time", type=float, default=0.0, help="Start time in seconds (default: 0)")
    parser.add_argument("--min-duration", type=float, default=2.0, help="Minimum pause duration in seconds (default: 2)")
    parser.add_argument("--window-size", type=float, default=30.0, help="Local window size in seconds (default: 30)")
    parser.add_argument("--threshold-ratio", type=float, default=0.5, help="Local threshold ratio (default: 0.5)")
    parser.add_argument(
        "--noise-floor-percentile",
        type=float,
        default=10.0,
        help="Percentile used to estimate noise floor (default: 10)",
    )
    parser.add_argument(
        "--noise-floor-multiplier",
        type=float,
        default=1.8,
        help="Multiplier on noise floor for absolute threshold (default: 1.8)",
    )
    parser.add_argument(
        "--global-cap-ratio",
        type=float,
        default=0.5,
        help="Cap absolute threshold as global_median * ratio (default: 0.5)",
    )
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.0,
        help="Merge detected pauses separated by <= this gap in seconds (default: 0)",
    )
    parser.add_argument(
        "--smoothing-seconds",
        type=float,
        default=1.0,
        help="Smooth energies over this many seconds before thresholding (default: 1.0)",
    )
    parser.add_argument(
        "--no-allow-local-only",
        action="store_true",
        help="Require BOTH local threshold and absolute noise-floor gate (more conservative)",
    )
    parser.add_argument(
        "--round-ndigits",
        type=int,
        default=3,
        help="Round start/end/duration to this many decimals in output (default: 3)",
    )

    args = parser.parse_args()

    print(f"Detecting pauses from: {args.energies}")

    with open(args.energies, encoding="utf-8") as f:
        energy_data: Dict[str, Any] = json.load(f)

    energies = [float(v) for v in energy_data.get("energies", [])]
    window_seconds = float(energy_data.get("window_seconds", 1.0))

    segments, analysis = detect_pauses_seconds(
        energies,
        window_seconds=window_seconds,
        start_time_seconds=args.start_time,
        min_duration_seconds=args.min_duration,
        window_size_seconds=args.window_size,
        threshold_ratio=args.threshold_ratio,
        noise_floor_percentile=args.noise_floor_percentile,
        noise_floor_multiplier=args.noise_floor_multiplier,
        global_cap_ratio=args.global_cap_ratio,
        merge_gap_seconds=args.merge_gap,
        smoothing_seconds=args.smoothing_seconds,
        allow_local_only=(not bool(args.no_allow_local_only)),
    )

    # Round output values to keep JSON stable and easy to read.
    nd = int(args.round_ndigits)
    rounded = [
        {"start": round(s["start"], nd), "end": round(s["end"], nd), "duration": round(s["duration"], nd)}
        for s in segments
    ]

    total_duration = sum(s["duration"] for s in rounded)

    result = {
        "method": "energy_local_median_with_noise_floor_gate",
        "segments": rounded,
        "total_segments": len(rounded),
        "total_duration_seconds": round(total_duration, nd),
        "parameters": {
            "start_time_seconds": args.start_time,
            "min_duration_seconds": args.min_duration,
            "window_size_seconds": args.window_size,
            "threshold_ratio": args.threshold_ratio,
            "noise_floor_percentile": args.noise_floor_percentile,
            "noise_floor_multiplier": args.noise_floor_multiplier,
            "global_cap_ratio": args.global_cap_ratio,
            "merge_gap_seconds": args.merge_gap,
            "round_ndigits": nd,
        },
        "analysis": {k: round(float(v), nd) for k, v in analysis.items()},
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nFound {result['total_segments']} pauses totaling {result['total_duration_seconds']}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
