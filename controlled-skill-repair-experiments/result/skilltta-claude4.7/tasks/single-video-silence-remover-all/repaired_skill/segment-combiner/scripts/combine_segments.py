#!/usr/bin/env python3
"""
Segment combiner - merges multiple segment detection results into a unified,
sorted, de-overlapped list.

Interval convention: half-open [start, end) in seconds.
Merge rule: after sorting by start, two segments are merged when
``next.start <= current.end + gap_tolerance`` (default 0.3s). This also
handles exact overlaps and containment.
When ``--duration`` is supplied, all segments are additionally clamped to
``[0, duration]`` and segments that collapse to zero length are dropped.
"""

import argparse
import json


def _load_raw(segment_files):
    segments = []
    for filepath in segment_files:
        with open(filepath) as f:
            data = json.load(f)
        if "segments" in data:
            for seg in data["segments"]:
                segments.append({"start": float(seg["start"]), "end": float(seg["end"])})
    return segments


def merge_segments(segments, gap_tolerance=0.3, total_duration=None):
    """Sort, merge overlapping/adjacent intervals, and optionally clamp."""
    if not segments:
        return []

    # Normalize and sort
    norm = []
    for s in segments:
        start = float(s["start"])
        end = float(s["end"])
        if end > start:
            norm.append({"start": start, "end": end})
    norm.sort(key=lambda x: x["start"])

    # Merge pass
    merged = [dict(norm[0])]
    for s in norm[1:]:
        last = merged[-1]
        if s["start"] <= last["end"] + gap_tolerance:
            if s["end"] > last["end"]:
                last["end"] = s["end"]
        else:
            merged.append(dict(s))

    # Clamp to [0, total_duration] if supplied
    if total_duration is not None:
        clamped = []
        for s in merged:
            start = max(0.0, s["start"])
            end = min(float(total_duration), s["end"])
            if end > start:
                clamped.append({"start": start, "end": end})
        merged = clamped

    # Recompute duration
    for s in merged:
        s["duration"] = s["end"] - s["start"]

    return merged


def combine_segments(segment_files, gap_tolerance=0.3, total_duration=None):
    raw = _load_raw(segment_files)
    merged = merge_segments(raw, gap_tolerance=gap_tolerance, total_duration=total_duration)
    total_dur = sum(s["duration"] for s in merged)
    return {
        "segments": merged,
        "total_segments": len(merged),
        "total_duration_seconds": total_dur,
        "parameters": {
            "gap_tolerance": gap_tolerance,
            "clamped_to_duration": total_duration,
            "interval_convention": "half_open_[start,end)",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Combine segment detection results")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment files to combine")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    parser.add_argument("--gap-tolerance", type=float, default=0.3,
                        help="Merge two segments when next.start <= current.end + tolerance (default: 0.3s)")
    parser.add_argument("--duration", type=float, default=None,
                        help="If provided, clamp all segments to [0, duration]")

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")
    print(f"  Gap tolerance: {args.gap_tolerance}s")
    if args.duration is not None:
        print(f"  Clamp to: [0, {args.duration}s]")

    result = combine_segments(args.segments, gap_tolerance=args.gap_tolerance, total_duration=args.duration)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined {result['total_segments']} segments (after merge)")
    print(f"Total duration to remove: {result['total_duration_seconds']:.2f}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
