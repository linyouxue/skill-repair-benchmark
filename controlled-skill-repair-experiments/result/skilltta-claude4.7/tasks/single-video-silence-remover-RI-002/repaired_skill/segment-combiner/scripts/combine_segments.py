#!/usr/bin/env python3
"""
Segment combiner - merges multiple segment detection results into a unified
list of sorted, non-overlapping half-open [start, end) intervals.

Contract (shared with video-processor and skilltta-task-guidance):
- Intervals are half-open [start, end), floats, in seconds.
- Sort by start ascending.
- Merge two intervals when next.start - current.end <= GAP_EPS (default 0.2s).
- Recompute duration = end - start on merged intervals.
- Recompute total_duration_seconds from the merged list.
- Drop invalid entries (end <= start) and clamp start to >= 0.
"""

import argparse
import json

DEFAULT_GAP_EPS = 0.2


def _normalize_raw(raw_segments):
    """Coerce to floats, clamp start>=0, drop invalid, sort by start."""
    normalized = []
    for seg in raw_segments:
        try:
            start = float(seg["start"])
            end = float(seg["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if start < 0:
            start = 0.0
        if end <= start:
            # Invalid or zero-length interval; skip.
            continue
        normalized.append({"start": start, "end": end})
    normalized.sort(key=lambda x: x["start"])
    return normalized


def merge_intervals(segments, gap_eps=DEFAULT_GAP_EPS):
    """Merge sorted half-open intervals when the gap is <= gap_eps.

    Returns a list of dicts {start, end, duration} that is sorted,
    strictly non-overlapping (a.end < b.start for consecutive a,b), and
    has end > start for every entry.
    """
    normalized = _normalize_raw(segments)
    if not normalized:
        return []

    merged = []
    cur = dict(normalized[0])
    for nxt in normalized[1:]:
        if nxt["start"] - cur["end"] <= gap_eps:
            if nxt["end"] > cur["end"]:
                cur["end"] = nxt["end"]
        else:
            cur["duration"] = cur["end"] - cur["start"]
            merged.append(cur)
            cur = dict(nxt)
    cur["duration"] = cur["end"] - cur["start"]
    merged.append(cur)
    return merged


def combine_segments(segment_files, gap_eps=DEFAULT_GAP_EPS, min_duration=None):
    """Combine, sort, and merge segments from multiple detection files."""
    raw = []
    for filepath in segment_files:
        with open(filepath) as f:
            data = json.load(f)
        if "segments" in data:
            for seg in data["segments"]:
                if "start" in seg and "end" in seg:
                    raw.append({"start": seg["start"], "end": seg["end"]})

    merged = merge_intervals(raw, gap_eps=gap_eps)

    if min_duration is not None:
        merged = [s for s in merged if s["duration"] >= min_duration]

    total_duration = sum(s["duration"] for s in merged)

    return {
        "segments": merged,
        "total_segments": len(merged),
        "total_duration_seconds": total_duration,
        "parameters": {"gap_eps": gap_eps, "min_duration": min_duration},
    }


def main():
    parser = argparse.ArgumentParser(description="Combine segment detection results")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment files to combine")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    parser.add_argument("--gap-eps", type=float, default=DEFAULT_GAP_EPS,
                        help="Merge adjacent intervals when gap <= this many seconds (default: 0.2)")
    parser.add_argument("--min-duration", type=float, default=None,
                        help="Optional minimum merged duration to retain; no default drop")

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")
    print(f"  gap_eps: {args.gap_eps}s")
    if args.min_duration is not None:
        print(f"  min_duration: {args.min_duration}s")

    result = combine_segments(args.segments, gap_eps=args.gap_eps, min_duration=args.min_duration)

    # Sanity validation before writing: strict non-overlap and end>start.
    segs = result["segments"]
    for i, s in enumerate(segs):
        assert s["end"] > s["start"], f"Invalid interval at index {i}: {s}"
        if i > 0:
            prev = segs[i - 1]
            assert prev["end"] < s["start"], (
                f"Overlap/touch after merge between {prev} and {s}; gap_eps may be too small"
            )

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined and merged into {result['total_segments']} segments")
    print(f"Total duration to remove: {result['total_duration_seconds']:.2f}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
