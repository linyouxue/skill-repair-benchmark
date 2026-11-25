#!/usr/bin/env python3
""" 
Segment combiner - merges multiple segment detection results into a unified list.

Contract:
- Time unit: seconds (float)
- Interval convention: half-open [start, end)
- duration = end - start (recomputed)

This script:
- loads segments from one or more JSON files,
- normalizes numeric start/end,
- optionally clamps to [0, duration],
- merges overlapping/adjacent segments (next.start <= cur.end + eps),
- recomputes duration from merged boundaries.

Note: This combiner **does not add new metadata fields** (to avoid surprising downstream
consumers). It preserves existing extra keys when possible, but correctness of
start/end/duration is the priority.
"""

import argparse
import json
import math
from typing import Any, Dict, List, Optional


def _coerce_float(x: Any, field: str, src: str) -> float:
    try:
        v = float(x)
    except Exception as e:
        raise ValueError(f"Invalid {field}={x!r} in {src}") from e
    if not math.isfinite(v):
        raise ValueError(f"Non-finite {field}={x!r} in {src}")
    return v


def _normalize_one_segment(seg: Any, src: str) -> Optional[Dict[str, Any]]:
    if not isinstance(seg, dict):
        return None
    if "start" not in seg or "end" not in seg:
        return None

    start = _coerce_float(seg.get("start"), "start", src)
    end = _coerce_float(seg.get("end"), "end", src)
    if not (end > start):
        return None

    out = dict(seg)  # preserve existing extra fields
    out["start"] = float(start)
    out["end"] = float(end)
    out["duration"] = float(end - start)
    return out


def _clamp(seg: Dict[str, Any], duration: float) -> Optional[Dict[str, Any]]:
    start = max(0.0, min(float(seg["start"]), float(duration)))
    end = max(0.0, min(float(seg["end"]), float(duration)))
    if end <= start:
        return None
    out = dict(seg)
    out["start"] = float(start)
    out["end"] = float(end)
    out["duration"] = float(end - start)
    return out


def merge_segments(segments: List[Dict[str, Any]], eps: float = 1e-3) -> List[Dict[str, Any]]:
    """Merge overlapping or adjacent segments.

    Two segments are merged if next.start <= cur.end + eps.
    Output is sorted and non-overlapping.
    """
    if not segments:
        return []

    segs = sorted(segments, key=lambda s: (float(s["start"]), float(s["end"])))
    merged: List[Dict[str, Any]] = []

    cur = dict(segs[0])
    cur["start"] = float(cur["start"])
    cur["end"] = float(cur["end"])

    for seg in segs[1:]:
        s0 = float(seg["start"])
        s1 = float(seg["end"])
        if s0 <= float(cur["end"]) + float(eps):
            # merge boundaries
            cur["end"] = max(float(cur["end"]), s1)
            # If both have 'type' and they disagree, drop 'type' to avoid misleading.
            if "type" in cur and "type" in seg and cur.get("type") != seg.get("type"):
                cur.pop("type", None)
        else:
            cur["duration"] = float(cur["end"] - cur["start"])
            merged.append(cur)
            cur = dict(seg)
            cur["start"] = float(cur["start"])
            cur["end"] = float(cur["end"])

    cur["duration"] = float(cur["end"] - cur["start"])
    merged.append(cur)

    # Final defensive duration recompute
    for s in merged:
        s["duration"] = float(float(s["end"]) - float(s["start"]))

    return merged


def combine_segments(segment_files: List[str], *, clamp_duration: Optional[float] = None, eps: float = 1e-3) -> Dict[str, Any]:
    raw: List[Dict[str, Any]] = []

    for filepath in segment_files:
        with open(filepath) as f:
            data = json.load(f)

        if isinstance(data, dict) and "segments" in data:
            items = data.get("segments", [])
        elif isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
        else:
            items = []

        for seg in items:
            norm = _normalize_one_segment(seg, filepath)
            if norm is not None:
                raw.append(norm)

    if clamp_duration is not None:
        cd = float(clamp_duration)
        clamped: List[Dict[str, Any]] = []
        for seg in raw:
            s2 = _clamp(seg, cd)
            if s2 is not None:
                clamped.append(s2)
        raw = clamped

    merged = merge_segments(raw, eps=float(eps))
    total_duration = float(sum(float(s["duration"]) for s in merged))

    return {
        "segments": merged,
        "total_segments": len(merged),
        "total_duration_seconds": total_duration,
        "parameters": {"eps": float(eps), "clamp_duration": float(clamp_duration) if clamp_duration is not None else None},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine segment detection results")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment files to combine")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    parser.add_argument("--duration", type=float, default=None, help="Optional clamp duration in seconds")
    parser.add_argument("--eps", type=float, default=1e-3, help="Merge epsilon in seconds (default: 1e-3)")

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")

    result = combine_segments(args.segments, clamp_duration=args.duration, eps=args.eps)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined {result['total_segments']} segments")
    print(f"Total duration to remove (merged): {result['total_duration_seconds']:.3f}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
