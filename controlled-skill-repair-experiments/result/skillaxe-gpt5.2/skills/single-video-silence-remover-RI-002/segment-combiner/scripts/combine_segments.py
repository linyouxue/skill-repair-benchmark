#!/usr/bin/env python3
"""
Segment combiner - merges multiple segment detection results into unified list.

Produces a normalized removal list:
- sorted by start
- clamped (optional)
- merged for overlaps/adjacency
- duration recomputed as end-start
"""

import argparse
import json
from typing import List, Optional, Dict, Any


def _to_float(x):
    try:
        return float(x)
    except Exception:
        return None


def normalize_and_merge_segments(
    segments: List[Dict[str, Any]],
    total_duration: Optional[float] = None,
    merge_gap: float = 0.05,
) -> List[Dict[str, float]]:
    """Validate, optionally clamp, then merge overlapping/adjacent segments.

    Args:
        segments: list of dicts with at least start/end (duration optional)
        total_duration: if provided, clamp to [0,total_duration]
        merge_gap: merge if next.start <= current.end + merge_gap

    Returns:
        List of merged segments with float start/end and duration=end-start.
    """

    cleaned: List[Dict[str, float]] = []
    for seg in segments:
        s = _to_float(seg.get("start"))
        e = _to_float(seg.get("end"))
        if s is None or e is None:
            continue

        # Clamp if requested
        if total_duration is not None:
            s = max(0.0, min(s, float(total_duration)))
            e = max(0.0, min(e, float(total_duration)))

        if e <= s:
            continue

        cleaned.append({"start": s, "end": e})

    cleaned.sort(key=lambda x: (x["start"], x["end"]))

    merged: List[Dict[str, float]] = []
    for seg in cleaned:
        if not merged:
            merged.append(seg)
            continue

        last = merged[-1]
        if seg["start"] <= last["end"] + merge_gap:
            last["end"] = max(last["end"], seg["end"])
        else:
            merged.append(seg)

    # Recompute durations
    out: List[Dict[str, float]] = []
    for seg in merged:
        out.append(
            {
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "duration": float(seg["end"] - seg["start"]),
            }
        )
    return out


def combine_segments(segment_files: List[str], total_duration: Optional[float] = None, merge_gap: float = 0.05):
    """Combine segments from multiple detection files."""
    segments: List[Dict[str, Any]] = []

    for filepath in segment_files:
        with open(filepath) as f:
            data = json.load(f)

        # Extract segments from the file
        if isinstance(data, dict) and "segments" in data:
            segments.extend(data["segments"])
        elif isinstance(data, list):
            segments.extend(data)
        elif isinstance(data, dict) and ("start" in data and "end" in data):
            segments.append(data)

    merged = normalize_and_merge_segments(segments, total_duration=total_duration, merge_gap=merge_gap)
    total_remove = sum(s["duration"] for s in merged)

    return {"segments": merged, "total_segments": len(merged), "total_duration_seconds": total_remove}


def main():
    parser = argparse.ArgumentParser(description="Combine segment detection results")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment files to combine")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    parser.add_argument(
        "--total-duration",
        type=float,
        default=None,
        help="Optional total duration (seconds) to clamp segments into [0,total_duration]",
    )
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.05,
        help="Merge adjacent segments if next.start <= current.end + merge_gap (default: 0.05s)",
    )

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")
    if args.total_duration is not None:
        print(f"  Clamping to duration: {args.total_duration}s")
    print(f"  Merge gap: {args.merge_gap}s")

    result = combine_segments(args.segments, total_duration=args.total_duration, merge_gap=args.merge_gap)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined {result['total_segments']} segments")
    print(f"Total duration to remove: {result['total_duration_seconds']:.3f}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
