#!/usr/bin/env python3
"""segment-combiner

Merge multiple segment JSON files into a single, normalized removal list.

This skill is designed to sit between detectors (opening / pause / silence) and the
video processor.

Supported input JSON shapes:

1) {"segments": [ {"start": ..., "end": ..., "duration": ...?}, ... ]}
2) [ {"start": ..., "end": ..., "duration": ...?}, ... ]
3) {"start": ..., "end": ..., "duration": ...?}

The output always uses the dict-with-"segments" shape and guarantees:
- segments are sorted by (start, end)
- segments are non-overlapping (overlaps/adjacent gaps are merged)
- every segment has numeric start/end/duration with duration == end - start

Time convention: seconds on the original timeline, with half-open intervals:
[start, end). (start is inclusive, end is exclusive)
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Iterable, List, Optional


def _load_segments(path: str) -> List[Dict[str, Any]]:
    """Load a list of segment dicts from a JSON file."""
    with open(path) as f:
        data = json.load(f)

    if isinstance(data, dict) and "segments" in data:
        segments = data["segments"]
    elif isinstance(data, list):
        segments = data
    elif isinstance(data, dict) and "start" in data and "end" in data:
        segments = [data]
    else:
        raise ValueError(
            f"{path}: unsupported segment JSON format. Expected a dict with 'segments', "
            "a list of segments, or a single segment dict with 'start'/'end'."
        )

    if not isinstance(segments, list):
        raise ValueError(f"{path}: 'segments' must be a JSON array")

    out: List[Dict[str, Any]] = []
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            raise ValueError(f"{path}: segment #{i} is not an object")
        out.append(seg)

    return out


def _coerce_float(value: Any, *, path: str, field: str) -> float:
    """Coerce numeric JSON values to float with a helpful error."""
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"{path}: segment field '{field}' must be a number; got {type(value).__name__}")


def _normalize_segment(
    seg: Dict[str, Any],
    *,
    path: str,
    clamp_end: Optional[float],
) -> Optional[Dict[str, Any]]:
    """Normalize a single segment.

    - clamps start to >= 0
    - optionally clamps end to <= clamp_end
    - drops invalid/empty segments
    - recomputes duration as end - start

    Returns None if the segment becomes invalid.
    """
    start = _coerce_float(seg.get("start"), path=path, field="start")
    end = _coerce_float(seg.get("end"), path=path, field="end")

    # Clamp to valid timeline bounds.
    start = max(0.0, start)
    if clamp_end is not None:
        end = min(clamp_end, end)

    if end <= start:
        return None

    # Preserve any extra fields (e.g., detector metadata), but ensure the required
    # numeric fields are canonical.
    normalized = {k: v for k, v in seg.items() if k not in {"start", "end", "duration"}}
    normalized.update({"start": start, "end": end, "duration": end - start})
    return normalized


def _merge_segments(segments: List[Dict[str, Any]], *, merge_gap: float) -> List[Dict[str, Any]]:
    """Merge overlapping/adjacent segments.

    Two segments are merged when next.start <= current.end + merge_gap.

    merge_gap=0 merges touching segments (e.g., [0,1) + [1,2) -> [0,2)).
    """
    if not segments:
        return []

    merged: List[Dict[str, Any]] = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        if seg["start"] <= prev["end"] + merge_gap:
            prev["end"] = max(prev["end"], seg["end"])
            prev["duration"] = prev["end"] - prev["start"]
            continue
        merged.append(seg)

    return merged


def combine_segments(
    segment_files: Iterable[str],
    *,
    merge_gap: float = 0.0,
    clamp_end: Optional[float] = None,
) -> Dict[str, Any]:
    """Combine and normalize segments from multiple files."""
    collected: List[Dict[str, Any]] = []

    for filepath in segment_files:
        for seg in _load_segments(filepath):
            normalized = _normalize_segment(seg, path=filepath, clamp_end=clamp_end)
            if normalized is not None:
                collected.append(normalized)

    collected.sort(key=lambda s: (s["start"], s["end"]))
    merged = _merge_segments(collected, merge_gap=merge_gap)

    total_duration = sum(float(s["duration"]) for s in merged)

    return {
        "segments": merged,
        "total_segments": len(merged),
        "total_duration_seconds": total_duration,
        "parameters": {
            "merge_gap": merge_gap,
            "clamp_end": clamp_end,
        },
        "source_files": list(segment_files),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine and normalize segment detection results")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment JSON files to combine")
    parser.add_argument("--output", required=True, help="Path to output combined segments JSON")
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.0,
        help=(
            "Merge segments whose gap is <= this many seconds (default: 0). "
            "Use a small value like 0.01 to absorb rounding artifacts."
        ),
    )
    parser.add_argument(
        "--clamp-end",
        type=float,
        default=None,
        help="Optional maximum timestamp to clamp segment ends (e.g., the video duration).",
    )

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")

    result = combine_segments(args.segments, merge_gap=args.merge_gap, clamp_end=args.clamp_end)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined into {result['total_segments']} segment(s)")
    print(f"Total duration to remove: {result['total_duration_seconds']:.2f}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
