#!/usr/bin/env python3
"""report-generator

Generate a compression report for a "remove segments from video" workflow.

Why this exists:
- The task schema expects:
  - original_duration_seconds
  - compressed_duration_seconds
  - removed_duration_seconds
  - compression_percentage
  - segments_removed [{start,end,duration}, ...]

This script:
- Measures durations using ffprobe (preferred for accuracy).
- Loads one or more segment JSON files.
- Normalizes segments (coerce -> clip -> sort -> merge -> recompute duration)
  so the reported segments are valid and non-overlapping.

It intentionally avoids third-party Python deps.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _require_ffprobe() -> None:
    """Raise a helpful error if ffprobe is not available."""

    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        raise RuntimeError(
            "ffprobe not found. Install ffmpeg (which provides ffprobe) and ensure it is on PATH."
        ) from e


def get_duration(video_path: str) -> float:
    """Get media duration using ffprobe."""

    _require_ffprobe()
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {video_path}: {result.stderr.strip()}")
    try:
        return float(result.stdout.strip())
    except ValueError as e:
        raise RuntimeError(f"ffprobe returned non-numeric duration for {video_path}: {result.stdout!r}") from e


def _load_segments_from_json(path: str) -> List[Dict[str, Any]]:
    """Load a segment list from a JSON file.

    Accepted formats:
    - {"segments": [ ... ]}
    - [ ... ]
    - {"start": ..., "end": ...}

    The returned list is *raw* (no validation beyond basic structure).
    """

    data: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "segments" in data:
        segs = data.get("segments", [])
    elif isinstance(data, list):
        segs = data
    elif isinstance(data, dict):
        segs = [data]
    else:
        segs = []

    out: List[Dict[str, Any]] = []
    if isinstance(segs, list):
        for seg in segs:
            if isinstance(seg, dict):
                out.append(seg)
    return out


def _coerce_pairs(raw_segments: Iterable[Dict[str, Any]]) -> List[Tuple[float, float]]:
    pairs: List[Tuple[float, float]] = []
    for seg in raw_segments:
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


def _normalize_pairs(
    pairs: List[Tuple[float, float]],
    *,
    duration_seconds: float,
    merge_gap: float = 0.0,
    min_duration: float = 0.0,
) -> List[Tuple[float, float]]:
    """Coerce -> clip -> sort -> merge -> filter."""

    dur = max(0.0, float(duration_seconds))
    merge_gap = max(0.0, float(merge_gap))
    min_duration = max(0.0, float(min_duration))

    # Clip to [0, dur]
    clipped: List[Tuple[float, float]] = []
    for s, e in pairs:
        s = max(0.0, float(s))
        e = min(dur, float(e))
        if e > s:
            clipped.append((s, e))

    if not clipped:
        return []

    clipped.sort(key=lambda x: (x[0], x[1]))

    merged: List[List[float]] = [[clipped[0][0], clipped[0][1]]]
    for s, e in clipped[1:]:
        ps, pe = merged[-1]
        if s <= pe + merge_gap:
            merged[-1][1] = max(pe, e)
        else:
            merged.append([s, e])

    out: List[Tuple[float, float]] = []
    for s, e in merged:
        if (e - s) + 1e-12 < min_duration:
            continue
        out.append((float(s), float(e)))

    return out


def _round_segments(
    pairs: List[Tuple[float, float]],
    *,
    round_ndigits: int,
    min_duration: float = 0.0,
    max_end: Optional[float] = None,
) -> List[Dict[str, float]]:
    """Round segments while preserving internal consistency.

    - Rounds start/end.
    - Recomputes duration from the rounded values.
    - Re-clips end to max_end (if provided) after rounding.
    """

    nd = int(round_ndigits)
    min_duration = max(0.0, float(min_duration))

    out: List[Dict[str, float]] = []
    for s, e in pairs:
        rs = round(float(s), nd)
        re = round(float(e), nd)
        if max_end is not None:
            re = min(re, round(float(max_end), nd))
        if re <= rs:
            continue
        dur = round(re - rs, nd)
        if dur + 1e-12 < min_duration:
            continue
        out.append({"start": rs, "end": re, "duration": dur})

    # Ensure sorted output.
    out.sort(key=lambda x: (x["start"], x["end"]))

    # Ensure no overlaps after rounding.
    fixed: List[Dict[str, float]] = []
    for seg in out:
        if not fixed:
            fixed.append(seg)
            continue
        prev = fixed[-1]
        if seg["start"] < prev["end"]:
            # Merge any overlap created by rounding.
            prev_end = max(prev["end"], seg["end"])
            prev["end"] = prev_end
            prev["duration"] = round(prev["end"] - prev["start"], nd)
        else:
            fixed.append(seg)
    return fixed


def generate_report(
    original_path: str,
    compressed_path: str,
    segments_paths: Optional[List[str]] = None,
    *,
    merge_gap: float = 0.0,
    min_segment_duration: float = 0.0,
    round_ndigits: int = 3,
) -> Dict[str, Any]:
    """Generate a compression report matching the task schema."""

    original_duration = get_duration(original_path)
    compressed_duration = get_duration(compressed_path)
    removed_duration = max(0.0, original_duration - compressed_duration)
    compression_pct = (removed_duration / original_duration) * 100.0 if original_duration else 0.0

    segments_out: List[Dict[str, float]] = []
    if segments_paths:
        raw: List[Dict[str, Any]] = []
        for p in segments_paths:
            raw.extend(_load_segments_from_json(p))

        pairs = _coerce_pairs(raw)
        normalized = _normalize_pairs(
            pairs,
            duration_seconds=original_duration,
            merge_gap=merge_gap,
            min_duration=min_segment_duration,
        )
        segments_out = _round_segments(
            normalized,
            round_ndigits=round_ndigits,
            min_duration=min_segment_duration,
            max_end=original_duration,
        )

    nd = int(round_ndigits)

    return {
        "original_duration_seconds": round(original_duration, nd),
        "compressed_duration_seconds": round(compressed_duration, nd),
        "removed_duration_seconds": round(removed_duration, nd),
        "compression_percentage": round(compression_pct, nd),
        "segments_removed": segments_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate compression report")
    parser.add_argument("--original", required=True, help="Path to original video")
    parser.add_argument("--compressed", required=True, help="Path to compressed video")
    parser.add_argument(
        "--segments",
        nargs="*",
        default=None,
        help="One or more segment JSON files (optional)",
    )
    parser.add_argument("--output", required=True, help="Path to output report JSON")
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
        help="Round numeric outputs to this many decimals (default: 3)",
    )

    args = parser.parse_args()

    print("Generating compression report...")
    print(f"  Original:   {args.original}")
    print(f"  Compressed: {args.compressed}")
    if args.segments:
        print(f"  Segments:   {len(args.segments)} file(s)")

    report = generate_report(
        args.original,
        args.compressed,
        args.segments,
        merge_gap=args.merge_gap,
        min_segment_duration=args.min_duration,
        round_ndigits=args.round_ndigits,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\nOriginal:   {report['original_duration_seconds']}s")
    print(f"Compressed: {report['compressed_duration_seconds']}s")
    print(f"Removed:    {report['removed_duration_seconds']}s")
    print(f"Compression: {report['compression_percentage']:.1f}%")
    print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()
