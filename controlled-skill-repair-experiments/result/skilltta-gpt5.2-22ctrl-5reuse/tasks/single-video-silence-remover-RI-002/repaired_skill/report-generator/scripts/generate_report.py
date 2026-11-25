#!/usr/bin/env python3
"""
Report generator - creates compression reports for video processing.

Repairs / hardening:
- If segments are provided, defensively normalizes + merges them and recomputes per-segment durations.
- Prefers segment-derived removed duration when it is consistent with measured media durations.
- Always keeps report math internally consistent (original ≈ compressed + removed), within a small tolerance.

The required task schema is preserved:
{
  "original_duration_seconds": <number>,
  "compressed_duration_seconds": <number>,
  "removed_duration_seconds": <number>,
  "compression_percentage": <number>,
  "segments_removed": [ {"start":<number>,"end":<number>,"duration":<number>} ]
}
"""

import argparse
import json
import subprocess
from typing import Any, Dict, Iterable, List, Optional


DURATION_TOLERANCE_SECONDS = 0.25


def get_duration(video_path: str) -> float:
    """Get video duration using ffprobe."""
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
        check=True,
    )
    return float(result.stdout.strip())


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _iter_segments_from_json(data: Any) -> Iterable[Dict[str, Any]]:
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


def normalize_segments(segments: List[Dict[str, Any]], total_duration: float) -> List[Dict[str, Any]]:
    """Clamp to [0,total_duration], drop invalid, recompute duration."""
    T = float(total_duration)
    out: List[Dict[str, Any]] = []

    for seg in segments:
        s = _to_float(seg.get("start"))
        e = _to_float(seg.get("end"))
        if s is None or e is None:
            continue

        s = max(0.0, min(float(s), T))
        e = max(0.0, min(float(e), T))
        if e <= s:
            continue

        cleaned = dict(seg)
        cleaned["start"] = s
        cleaned["end"] = e
        cleaned["duration"] = e - s
        out.append(cleaned)

    out.sort(key=lambda x: (x["start"], x["end"]))
    return out


def merge_segments(segments: List[Dict[str, Any]], merge_gap: float = 0.0) -> List[Dict[str, Any]]:
    """Merge overlapping / near-contiguous segments. Assumes sorted."""
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
            cur["end"] = max(cur_end, e)

            # Preserve stable type if consistent; otherwise drop it.
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
            cur["duration"] = float(cur["end"]) - float(cur["start"])
            merged.append(cur)
            cur = dict(seg)

    cur["duration"] = float(cur["end"]) - float(cur["start"])
    merged.append(cur)
    merged.sort(key=lambda x: (x["start"], x["end"]))
    return merged


def _sum_segment_durations(segments: List[Dict[str, Any]]) -> float:
    return float(sum(float(s["end"]) - float(s["start"]) for s in segments))


def generate_report(
    original_path: str,
    compressed_path: str,
    segments_path: Optional[str] = None,
    merge_gap: float = 0.0,
    tolerance_seconds: float = DURATION_TOLERANCE_SECONDS,
) -> Dict[str, Any]:
    """Generate compression report."""

    # Measure durations from actual media.
    original_duration = get_duration(original_path)
    compressed_duration_measured = get_duration(compressed_path)

    # Baseline (media-measured) removed duration.
    removed_duration_measured = max(0.0, original_duration - compressed_duration_measured)

    # Load + sanitize segments if provided.
    segments_removed: List[Dict[str, Any]] = []
    removed_duration_from_segments: Optional[float] = None

    if segments_path:
        with open(segments_path) as f:
            data = json.load(f)
        raw = list(_iter_segments_from_json(data))
        segments_removed = merge_segments(
            normalize_segments(raw, total_duration=original_duration),
            merge_gap=merge_gap,
        )
        removed_duration_from_segments = _sum_segment_durations(segments_removed)

    # Choose durations for the report.
    # Prefer segment-derived removed duration iff it agrees with measured durations.
    if removed_duration_from_segments is not None:
        compressed_est = max(0.0, original_duration - removed_duration_from_segments)
        if abs(compressed_est - compressed_duration_measured) <= float(tolerance_seconds):
            removed_duration = removed_duration_from_segments
            compressed_duration = compressed_est
        else:
            removed_duration = removed_duration_measured
            compressed_duration = compressed_duration_measured
    else:
        removed_duration = removed_duration_measured
        compressed_duration = compressed_duration_measured

    compression_pct = (removed_duration / original_duration) * 100 if original_duration > 0 else 0.0

    # Keep a modest precision to reduce rounding-driven inconsistencies.
    return {
        "original_duration_seconds": round(original_duration, 3),
        "compressed_duration_seconds": round(compressed_duration, 3),
        "removed_duration_seconds": round(removed_duration, 3),
        "compression_percentage": round(compression_pct, 3),
        "segments_removed": segments_removed,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate compression report")
    parser.add_argument("--original", required=True, help="Path to original video")
    parser.add_argument("--compressed", required=True, help="Path to compressed video")
    parser.add_argument("--segments", help="Path to segments JSON (optional)")
    parser.add_argument("--output", required=True, help="Path to output report JSON")
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.0,
        help="Merge overlaps and near-contiguous removed segments within this gap (seconds). Default: 0.0",
    )
    parser.add_argument(
        "--tolerance-seconds",
        type=float,
        default=DURATION_TOLERANCE_SECONDS,
        help=f"Tolerance for reconciling segment-derived durations with measured output (seconds). Default: {DURATION_TOLERANCE_SECONDS}",
    )

    args = parser.parse_args()

    print("Generating compression report...")
    print(f"  Original: {args.original}")
    print(f"  Compressed: {args.compressed}")
    if args.segments:
        print(f"  Segments: {args.segments}")

    report = generate_report(
        args.original,
        args.compressed,
        args.segments,
        merge_gap=args.merge_gap,
        tolerance_seconds=args.tolerance_seconds,
    )

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nOriginal: {report['original_duration_seconds']}s")
    print(f"Compressed: {report['compressed_duration_seconds']}s")
    print(f"Removed: {report['removed_duration_seconds']}s")
    print(f"Compression: {report['compression_percentage']:.3f}%")
    print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()
