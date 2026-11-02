#!/usr/bin/env python3
"""segment-combiner

Merge multiple segment JSON files into a single *normalized* removal list.

Why normalization matters
------------------------
Downstream video processing typically assumes removal segments are:

- sorted by start time
- non-overlapping
- expressed as half-open time ranges: [start, end) in seconds

Detector outputs (or multiple detector sources) may overlap or contain adjacent
ranges. This script merges overlaps/adjacent segments and recomputes durations
so that downstream processors can safely invert the removal list into keep
segments.

Input flexibility
-----------------
Each input file may be either:

- {"segments": [ ... ]}
- a raw JSON list: [ {"start": ..., "end": ...}, ... ]
- a single segment object: {"start": ..., "end": ...}

Only start/end are required; duration is recomputed as end - start.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Iterable, List, Tuple


_EPS = 1e-9


def _as_float(value: Any) -> float:
    """Best-effort numeric coercion."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value.strip())
    raise TypeError(f"Unsupported numeric value: {value!r}")


def _clean_number(x: float) -> int | float:
    """Prefer ints when very close; otherwise round for stability."""
    if abs(x - round(x)) <= 1e-6:
        return int(round(x))
    # millisecond precision is plenty for ffmpeg trim/atrim use
    return round(float(x), 3)


def _iter_segments(payload: Any) -> Iterable[Dict[str, Any]]:
    """Yield raw segment dicts from supported JSON payload shapes."""
    if isinstance(payload, dict) and "segments" in payload:
        segs = payload.get("segments")
        if isinstance(segs, list):
            for seg in segs:
                if isinstance(seg, dict):
                    yield seg
        return

    if isinstance(payload, list):
        for seg in payload:
            if isinstance(seg, dict):
                yield seg
        return

    if isinstance(payload, dict) and "start" in payload and "end" in payload:
        yield payload


def _normalize_segment(seg: Dict[str, Any]) -> Dict[str, float]:
    """Normalize a segment to {start,end,duration} floats (seconds)."""
    start = _as_float(seg["start"])
    end = _as_float(seg["end"])

    # Treat as half-open: [start, end). Require strictly positive duration.
    if end <= start:
        raise ValueError(f"Invalid segment (end <= start): start={start}, end={end}")

    return {"start": start, "end": end, "duration": end - start}


def _merge_sorted_segments(segments: List[Dict[str, float]], merge_gap: float = 0.0) -> List[Dict[str, float]]:
    """Merge overlapping/adjacent segments.

    Segments are treated as half-open [start,end). We merge when:
      next.start <= current.end + merge_gap

    merge_gap exists mainly to absorb floating-point rounding differences.
    """
    if not segments:
        return []

    merged: List[Dict[str, float]] = [dict(segments[0])]
    for seg in segments[1:]:
        cur = merged[-1]
        if seg["start"] <= cur["end"] + merge_gap + _EPS:
            cur["end"] = max(cur["end"], seg["end"])
            cur["duration"] = cur["end"] - cur["start"]
        else:
            merged.append(dict(seg))

    return merged


def combine_segments(segment_files: List[str], merge_gap: float = 0.0) -> Dict[str, Any]:
    """Combine and normalize segments from multiple detection files."""
    raw_segments: List[Dict[str, float]] = []
    skipped: List[Tuple[str, str]] = []

    for filepath in segment_files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for seg in _iter_segments(data):
            try:
                raw_segments.append(_normalize_segment(seg))
            except Exception as e:  # noqa: BLE001 - intentional best-effort ingestion
                skipped.append((filepath, str(e)))

    raw_segments.sort(key=lambda x: (x["start"], x["end"]))
    merged_segments = _merge_sorted_segments(raw_segments, merge_gap=merge_gap)

    # Clean numeric formatting for stable JSON and downstream expectations.
    cleaned_segments: List[Dict[str, Any]] = []
    for seg in merged_segments:
        start = float(seg["start"])
        end = float(seg["end"])
        cleaned_segments.append(
            {
                "start": _clean_number(start),
                "end": _clean_number(end),
                "duration": _clean_number(end - start),
            }
        )

    total_duration = sum(float(s["duration"]) for s in cleaned_segments)

    result: Dict[str, Any] = {
        "segments": cleaned_segments,
        "total_segments": len(cleaned_segments),
        "total_duration_seconds": _clean_number(total_duration),
        "parameters": {"merge_gap_seconds": merge_gap},
        "source_files": list(segment_files),
    }

    if skipped:
        result["skipped"] = [
            {
                "file": file,
                "reason": reason,
            }
            for file, reason in skipped
        ]

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine and normalize segment detection results")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment JSON file(s) to combine")
    parser.add_argument("--output", required=True, help="Path to output combined segments JSON")
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.0,
        help="Merge segments with gaps <= this many seconds (default: 0)",
    )

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")
    if args.merge_gap:
        print(f"  Merge gap tolerance: {args.merge_gap}s")

    result = combine_segments(args.segments, merge_gap=args.merge_gap)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nCombined {result['total_segments']} segment(s)")
    print(f"Total duration to remove: {result['total_duration_seconds']}s")
    if result.get("skipped"):
        print(f"Skipped {len(result['skipped'])} invalid segment(s)")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
