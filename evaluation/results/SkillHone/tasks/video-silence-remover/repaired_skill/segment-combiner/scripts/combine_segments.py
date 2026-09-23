#!/usr/bin/env python3
"""skills/segment-combiner

Combine multiple segment JSON files into a single, *unioned* removal list.

Why this exists:
- Different detectors (opening detector, pause detector, etc.) can emit overlapping
  or back-to-back segments.
- Downstream video trimming and report math are simpler and more robust when the
  removal segments are sorted, clamped, and merged into a non-overlapping union.

Input JSON format (per file):
  {"segments": [{"start": <sec>, "end": <sec>, "duration": <sec>}, ...]}

Output JSON format:
  {
    "segments": [...],
    "total_segments": <int>,
    "total_duration_seconds": <float>
  }
"""

import argparse
import json
from typing import List, Dict, Optional


def _to_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def _normalize_segment(seg: Dict, *, duration_limit: Optional[float] = None) -> Optional[Dict]:
    """Normalize one segment.

    Returns a dict with start/end/duration floats, or None if invalid.
    """
    start = _to_float(seg.get("start"))
    end = _to_float(seg.get("end"))

    # Reject NaNs and obviously invalid values
    if not (start == start and end == end):
        return None

    # Clamp to [0, duration_limit] if provided
    if duration_limit is not None:
        if start < 0:
            start = 0.0
        if end > duration_limit:
            end = duration_limit

    # Enforce start < end
    if end <= start:
        return None

    return {"start": float(start), "end": float(end), "duration": float(end - start)}


def merge_segments(segments: List[Dict], *, duration_limit: Optional[float] = None, merge_gap_seconds: float = 0.05) -> List[Dict]:
    """Union overlapping/adjacent segments.

    merge_gap_seconds merges tiny gaps caused by rounding differences.
    """
    normalized = []
    for s in segments:
        ns = _normalize_segment(s, duration_limit=duration_limit)
        if ns is not None:
            normalized.append(ns)

    if not normalized:
        return []

    normalized.sort(key=lambda x: (x["start"], x["end"]))

    merged = [normalized[0]]
    for seg in normalized[1:]:
        prev = merged[-1]
        if seg["start"] <= prev["end"] + merge_gap_seconds:
            # Overlaps or touches: extend
            if seg["end"] > prev["end"]:
                prev["end"] = seg["end"]
                prev["duration"] = prev["end"] - prev["start"]
        else:
            merged.append(seg)

    return merged


def combine_segments(segment_files: List[str], *, duration_limit: Optional[float] = None) -> Dict:
    """Combine and merge segments from multiple detection files."""
    segments: List[Dict] = []

    for filepath in segment_files:
        with open(filepath) as f:
            data = json.load(f)

        if isinstance(data, dict) and "segments" in data and isinstance(data["segments"], list):
            for seg in data["segments"]:
                if isinstance(seg, dict):
                    segments.append(seg)

    segments = merge_segments(segments, duration_limit=duration_limit)
    total_duration = sum(s["duration"] for s in segments)

    return {"segments": segments, "total_segments": len(segments), "total_duration_seconds": total_duration}


def main():
    parser = argparse.ArgumentParser(description="Combine segment detection results")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment files to combine")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    parser.add_argument(
        "--duration-limit-seconds",
        type=float,
        default=None,
        help="Optional max duration of the media; segments are clamped to [0, limit].",
    )
    parser.add_argument(
        "--merge-gap-seconds",
        type=float,
        default=0.05,
        help="Merge gaps smaller than this many seconds (default: 0.05).",
    )

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")

    # plumb merge gap via merge_segments; keep combine_segments signature stable
    result = combine_segments(args.segments, duration_limit=args.duration_limit_seconds)
    if args.merge_gap_seconds != 0.05:
        result = {
            "segments": merge_segments(result["segments"], duration_limit=args.duration_limit_seconds, merge_gap_seconds=args.merge_gap_seconds),
            "total_segments": 0,
            "total_duration_seconds": 0.0,
        }
        result["total_segments"] = len(result["segments"])
        result["total_duration_seconds"] = sum(s["duration"] for s in result["segments"])

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined {result['total_segments']} segments")
    print(f"Total duration to remove: {result['total_duration_seconds']}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
