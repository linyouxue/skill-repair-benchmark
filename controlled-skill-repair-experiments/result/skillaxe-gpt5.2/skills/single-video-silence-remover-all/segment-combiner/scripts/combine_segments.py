#!/usr/bin/env python3
"""Segment combiner - merges multiple segment detection results into unified list.

This tool is intentionally *normalizing*:
- Treats segments as half-open intervals [start, end)
- Sorts by start
- Optionally clamps to [0, total_duration]
- Merges overlaps and (optionally) small gaps
- Recomputes duration as end-start

Rationale: downstream video processing typically assumes removal segments are sorted and non-overlapping.
"""

import argparse
import json
from typing import List, Optional, Tuple


def _coerce_segment(seg) -> Optional[Tuple[float, float]]:
    """Return (start,end) as floats if valid, else None."""
    if not isinstance(seg, dict):
        return None
    if "start" not in seg or "end" not in seg:
        return None
    try:
        start = float(seg["start"])
        end = float(seg["end"])
    except (TypeError, ValueError):
        return None
    if not (start < end):
        return None
    return start, end


def normalize_and_merge(segments: List[Tuple[float, float]], total_duration: Optional[float] = None, merge_gap: float = 0.0):
    """Sort, clamp, and merge segments.

    Args:
      segments: list of (start,end)
      total_duration: if provided, clamp to [0,total_duration]
      merge_gap: merge if next.start <= cur.end + merge_gap

    Returns:
      merged list of dict segments with start/end/duration.
    """
    if total_duration is not None:
        total_duration = float(total_duration)

    cleaned: List[Tuple[float, float]] = []
    for s, e in segments:
        if total_duration is not None:
            s = max(0.0, min(s, total_duration))
            e = max(0.0, min(e, total_duration))
        if s < e:
            cleaned.append((s, e))

    cleaned.sort(key=lambda x: x[0])

    merged: List[Tuple[float, float]] = []
    gap = float(merge_gap)

    for s, e in cleaned:
        if not merged:
            merged.append((s, e))
            continue
        ps, pe = merged[-1]
        if s <= pe + gap:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))

    out = []
    for s, e in merged:
        out.append({"start": s, "end": e, "duration": e - s})
    return out


def combine_segments(segment_files, total_duration: Optional[float] = None, merge_gap: float = 0.0):
    """Combine segments from multiple detection files."""
    raw_pairs: List[Tuple[float, float]] = []

    for filepath in segment_files:
        with open(filepath) as f:
            data = json.load(f)

        seg_list = None
        if isinstance(data, dict) and "segments" in data:
            seg_list = data["segments"]
        elif isinstance(data, list):
            seg_list = data
        elif isinstance(data, dict) and "start" in data and "end" in data:
            seg_list = [data]

        if not seg_list:
            continue

        for seg in seg_list:
            pair = _coerce_segment(seg)
            if pair is not None:
                raw_pairs.append(pair)

    merged = normalize_and_merge(raw_pairs, total_duration=total_duration, merge_gap=merge_gap)
    total_duration_removed = sum(s["duration"] for s in merged)

    return {"segments": merged, "total_segments": len(merged), "total_duration_seconds": total_duration_removed}


def main():
    parser = argparse.ArgumentParser(description="Combine segment detection results")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment files to combine")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    parser.add_argument(
        "--total-duration",
        type=float,
        default=None,
        help="Optional total duration in seconds; if provided, segments are clamped to [0,total_duration].",
    )
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.0,
        help="Merge segments whose gap is <= this many seconds (default: 0).",
    )

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")

    result = combine_segments(args.segments, total_duration=args.total_duration, merge_gap=args.merge_gap)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined {result['total_segments']} segments")
    print(f"Total duration to remove: {result['total_duration_seconds']:.3f}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
