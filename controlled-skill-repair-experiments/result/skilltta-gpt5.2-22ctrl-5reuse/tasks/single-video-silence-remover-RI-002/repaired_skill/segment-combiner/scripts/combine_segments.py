#!/usr/bin/env python3
"""
Segment combiner - merges multiple segment detection results into a unified list.

Key behaviors:
- Accepts multiple input JSON formats (dict-with-segments, list-of-segments, single-segment dict).
- Normalizes segments (coerce numeric, optional clamp, drop invalid end<=start).
- Sorts and merges overlapping / near-contiguous intervals.
- Recomputes duration as end-start (never trusts input duration).

Interval convention: half-open [start, end) in seconds.
"""

import argparse
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _iter_segments_from_json(data: Any) -> Iterable[Dict[str, Any]]:
    """Yield segment dicts from supported JSON shapes."""
    if isinstance(data, dict) and "segments" in data and isinstance(data["segments"], list):
        for seg in data["segments"]:
            if isinstance(seg, dict):
                yield seg
    elif isinstance(data, list):
        for seg in data:
            if isinstance(seg, dict):
                yield seg
    elif isinstance(data, dict) and ("start" in data and "end" in data):
        yield data


def normalize_segments(
    segments: List[Dict[str, Any]],
    total_duration: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Coerce numeric times, optionally clamp to [0,total_duration], drop invalid."""

    out: List[Dict[str, Any]] = []
    for seg in segments:
        s = _to_float(seg.get("start"))
        e = _to_float(seg.get("end"))
        if s is None or e is None:
            continue

        if total_duration is not None:
            s = max(0.0, min(s, float(total_duration)))
            e = max(0.0, min(e, float(total_duration)))
        else:
            s = max(0.0, s)

        if e <= s:
            continue

        # Keep extra fields if present, but duration is always recomputed.
        cleaned = dict(seg)
        cleaned["start"] = s
        cleaned["end"] = e
        cleaned["duration"] = e - s
        out.append(cleaned)

    out.sort(key=lambda x: (x["start"], x["end"]))
    return out


def merge_segments(segments: List[Dict[str, Any]], merge_gap: float = 0.1) -> List[Dict[str, Any]]:
    """Merge overlapping and near-contiguous segments. Assumes input is sorted."""

    if not segments:
        return []

    gap = max(0.0, float(merge_gap))

    merged: List[Dict[str, Any]] = []
    cur = dict(segments[0])

    for seg in segments[1:]:
        s = float(seg["start"])
        e = float(seg["end"])
        cur_end = float(cur["end"])

        if s <= cur_end + gap:
            # Merge by extending end.
            new_end = max(cur_end, e)
            cur["end"] = new_end

            # Preserve a stable "type" only if consistent.
            if "type" in cur or "type" in seg:
                t1 = cur.get("type")
                t2 = seg.get("type")
                if t1 is None:
                    cur["type"] = t2
                elif t2 is None:
                    pass
                elif t1 != t2:
                    cur.pop("type", None)

            cur["duration"] = float(cur["end"]) - float(cur["start"])
        else:
            # Finalize current
            cur["duration"] = float(cur["end"]) - float(cur["start"])
            merged.append(cur)
            cur = dict(seg)

    cur["duration"] = float(cur["end"]) - float(cur["start"])
    merged.append(cur)

    # Ensure sorted and strictly non-overlapping after merge.
    merged.sort(key=lambda x: (x["start"], x["end"]))
    return merged


def combine_segments(segment_files: List[str], merge_gap: float = 0.1, total_duration: Optional[float] = None) -> Dict[str, Any]:
    """Combine segments from multiple detection files."""

    raw: List[Dict[str, Any]] = []
    for filepath in segment_files:
        with open(filepath) as f:
            data = json.load(f)
        raw.extend(list(_iter_segments_from_json(data)))

    normalized = normalize_segments(raw, total_duration=total_duration)
    merged = merge_segments(normalized, merge_gap=merge_gap)

    total_duration_seconds = sum(float(s["end"]) - float(s["start"]) for s in merged)

    return {
        "segments": merged,
        "total_segments": len(merged),
        "total_duration_seconds": total_duration_seconds,
        "parameters": {
            "merge_gap": float(merge_gap),
            "total_duration": float(total_duration) if total_duration is not None else None,
            "interval_convention": "half-open [start,end)",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Combine segment detection results")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment files to combine")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.1,
        help="Merge segments if next.start <= current.end + merge_gap (seconds). Default: 0.1",
    )
    parser.add_argument(
        "--total-duration",
        type=float,
        default=None,
        help="Optional clamp window [0,total_duration] in seconds (recommended when known).",
    )

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")

    result = combine_segments(args.segments, merge_gap=args.merge_gap, total_duration=args.total_duration)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined {result['total_segments']} segments")
    print(f"Total duration to remove: {result['total_duration_seconds']:.3f}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
