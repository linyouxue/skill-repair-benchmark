#!/usr/bin/env python3
"""
Segment combiner - merges multiple segment detection results into a normalized
interval union.

Contract on the output `segments` array (relied on by video-processor):
  * sorted by start ascending
  * clamped so start >= 0 and (if --total-duration is provided) end <= total_duration
  * no two intervals overlap or touch (end[i] < start[i+1])
  * every segment's duration equals end - start (recomputed, not trusted from input)
"""

import argparse
import json


def _coerce_int_if_exact(value):
    """Return int when value is an integer-valued float; preserves integer schema."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def normalize_segments(raw_segments, total_duration=None):
    """Clamp, sort, and merge overlapping/touching intervals into a disjoint union."""
    clamped = []
    for seg in raw_segments:
        start = max(0.0, float(seg["start"]))
        end = float(seg["end"])
        if total_duration is not None:
            end = min(end, float(total_duration))
            start = min(start, float(total_duration))
        if end <= start:
            continue  # drop degenerate intervals produced by clamping
        clamped.append({"start": start, "end": end})

    clamped.sort(key=lambda x: x["start"])

    # Merge overlapping OR touching intervals (end >= next.start means merge).
    merged = []
    for seg in clamped:
        if merged and seg["start"] <= merged[-1]["end"]:
            if seg["end"] > merged[-1]["end"]:
                merged[-1]["end"] = seg["end"]
        else:
            merged.append({"start": seg["start"], "end": seg["end"]})

    # Recompute duration and coerce back to int where inputs were integer seconds.
    for seg in merged:
        seg["duration"] = seg["end"] - seg["start"]
        seg["start"] = _coerce_int_if_exact(seg["start"])
        seg["end"] = _coerce_int_if_exact(seg["end"])
        seg["duration"] = _coerce_int_if_exact(seg["duration"])

    return merged


def combine_segments(segment_files, total_duration=None):
    """Combine segments from multiple detection files into a normalized union."""
    raw = []

    for filepath in segment_files:
        with open(filepath) as f:
            data = json.load(f)

        if "segments" in data:
            for seg in data["segments"]:
                raw.append({"start": seg["start"], "end": seg["end"]})

    segments = normalize_segments(raw, total_duration=total_duration)
    total = sum(s["duration"] for s in segments)

    return {
        "segments": segments,
        "total_segments": len(segments),
        "total_duration_seconds": total,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Combine segment detection results into a normalized interval union"
    )
    parser.add_argument("--segments", nargs="+", required=True, help="Segment files to combine")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    parser.add_argument(
        "--total-duration",
        type=float,
        default=None,
        help="Optional video duration in seconds; segments are clamped to [0, total_duration]",
    )

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")
    if args.total_duration is not None:
        print(f"  Clamping to [0, {args.total_duration}]s")

    result = combine_segments(args.segments, total_duration=args.total_duration)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined {result['total_segments']} normalized segments")
    print(f"Total duration to remove: {result['total_duration_seconds']}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
