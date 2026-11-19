#!/usr/bin/env python3
"""segment-combiner

Combine multiple segment JSON files into a single, normalized segments list.

Why this exists:
- Different detectors may output overlapping/adjacent segments.
- Some detectors may omit `duration`.
- Downstream video processing is much safer with a merged, sorted, de-overlapped list.

This script:
- Loads `segments` arrays from one or more JSON files (or a raw list / single dict).
- Validates and coerces start/end to floats.
- Optionally merges segments separated by a small gap.
- Recomputes `duration` as end-start for every output segment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _load_segments(path: str) -> List[Dict[str, Any]]:
    data: Any = json.loads(Path(path).read_text(encoding="utf-8"))

    if isinstance(data, dict) and "segments" in data:
        segs = data.get("segments")
    elif isinstance(data, list):
        segs = data
    elif isinstance(data, dict):
        # Single segment dict
        segs = [data]
    else:
        raise ValueError(f"Unsupported segments JSON structure in {path}")

    if not isinstance(segs, list):
        raise ValueError(f"Expected a list of segments in {path}")

    out: List[Dict[str, Any]] = []
    for seg in segs:
        if isinstance(seg, dict):
            out.append(seg)
        else:
            raise ValueError(f"Segment entries must be objects with start/end fields (got {type(seg)})")
    return out


def _coerce_segments(raw: Iterable[Dict[str, Any]]) -> List[Tuple[float, float]]:
    pairs: List[Tuple[float, float]] = []
    for seg in raw:
        if "start" not in seg or "end" not in seg:
            continue
        try:
            s = float(seg["start"])
            e = float(seg["end"])
        except (TypeError, ValueError):
            continue
        if e <= s:
            continue
        pairs.append((s, e))
    return pairs


def _merge_pairs(pairs: List[Tuple[float, float]], merge_gap: float = 0.0) -> List[Tuple[float, float]]:
    if not pairs:
        return []

    merge_gap = max(0.0, float(merge_gap))
    pairs = sorted(pairs, key=lambda x: (x[0], x[1]))

    merged: List[List[float]] = [[pairs[0][0], pairs[0][1]]]
    for s, e in pairs[1:]:
        ps, pe = merged[-1]
        if s <= pe + merge_gap:
            merged[-1][1] = max(pe, e)
        else:
            merged.append([s, e])

    return [(float(s), float(e)) for s, e in merged]


def normalize_segments(
    raw_segments: Iterable[Dict[str, Any]],
    *,
    merge_gap: float = 0.0,
    min_start: float = 0.0,
    max_end: Optional[float] = None,
    min_duration: float = 0.0,
    round_ndigits: int = 3,
) -> List[Dict[str, float]]:
    """Normalize a set of raw segments.

    Returns a list of {start, end, duration} dictionaries with float values.
    """

    pairs = _coerce_segments(raw_segments)

    # Clip
    clipped: List[Tuple[float, float]] = []
    for s, e in pairs:
        s = max(float(min_start), s)
        if max_end is not None:
            e = min(float(max_end), e)
        if e > s:
            clipped.append((s, e))

    merged = _merge_pairs(clipped, merge_gap=merge_gap)

    out: List[Dict[str, float]] = []
    for s, e in merged:
        dur = e - s
        if dur + 1e-12 < float(min_duration):
            continue
        out.append(
            {
                "start": round(float(s), int(round_ndigits)),
                "end": round(float(e), int(round_ndigits)),
                "duration": round(float(dur), int(round_ndigits)),
            }
        )

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine multiple segment JSON files")
    parser.add_argument("--segments", nargs="+", required=True, help="Segment JSON files to combine")
    parser.add_argument("--output", required=True, help="Path to output combined segments JSON")
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.0,
        help="Merge segments separated by <= this many seconds (default: 0.0)",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.0,
        help="Drop segments shorter than this duration in seconds (default: 0.0)",
    )
    parser.add_argument(
        "--round-ndigits",
        type=int,
        default=3,
        help="Round start/end/duration to this many decimals (default: 3)",
    )

    args = parser.parse_args()

    print("Combining segments...")
    for f in args.segments:
        print(f"  Input: {f}")

    all_raw: List[Dict[str, Any]] = []
    for path in args.segments:
        all_raw.extend(_load_segments(path))

    combined = normalize_segments(
        all_raw,
        merge_gap=args.merge_gap,
        min_duration=args.min_duration,
        round_ndigits=args.round_ndigits,
    )

    result = {
        "segments": combined,
        "total_segments": len(combined),
        "total_duration_seconds": round(sum(s["duration"] for s in combined), args.round_ndigits),
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"\nCombined {result['total_segments']} segments")
    print(f"Total duration to remove: {result['total_duration_seconds']}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
