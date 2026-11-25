#!/usr/bin/env python3
""" 
Report generator - creates compression reports for video processing.

Produces the task-format JSON:
{
  "original_duration_seconds": <number>,
  "compressed_duration_seconds": <number>,
  "removed_duration_seconds": <number>,
  "compression_percentage": <number>,
  "segments_removed": [{"start":..., "end":..., "duration":...}, ...]
}

Notes:
- Durations are probed with ffprobe.
- If a segments file is provided, segments are normalized to numeric start/end,
  clamped to [0, original_duration], merged (overlap/adjacent), and duration is
  recomputed as (end-start).
- The top-level removed duration is computed as (original - compressed) to ensure
  the identity original ≈ compressed + removed holds using probed durations.
"""

import argparse
import json
import math
import subprocess
from typing import Any, Dict, List, Optional


EPS_DEFAULT = 1e-3


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


def _coerce_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return v


def _load_segments_any(segments_path: str) -> List[Dict[str, Any]]:
    with open(segments_path) as f:
        data = json.load(f)

    if isinstance(data, dict) and "segments" in data:
        items = data.get("segments", [])
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [data]
    else:
        items = []

    out: List[Dict[str, Any]] = []
    for seg in items:
        if not isinstance(seg, dict):
            continue
        s = _coerce_float(seg.get("start"))
        e = _coerce_float(seg.get("end"))
        if s is None or e is None:
            continue
        if e <= s:
            continue
        out.append({"start": float(s), "end": float(e)})
    return out


def _clamp_and_merge(segments: List[Dict[str, Any]], *, duration: float, eps: float = EPS_DEFAULT) -> List[Dict[str, float]]:
    cleaned: List[Dict[str, float]] = []

    for seg in segments:
        s = max(0.0, min(float(seg["start"]), float(duration)))
        e = max(0.0, min(float(seg["end"]), float(duration)))
        if e <= s:
            continue
        cleaned.append({"start": float(s), "end": float(e)})

    if not cleaned:
        return []

    cleaned.sort(key=lambda x: (x["start"], x["end"]))
    merged: List[Dict[str, float]] = []
    cur = dict(cleaned[0])

    for seg in cleaned[1:]:
        if float(seg["start"]) <= float(cur["end"]) + float(eps):
            cur["end"] = max(float(cur["end"]), float(seg["end"]))
        else:
            merged.append(cur)
            cur = dict(seg)

    merged.append(cur)

    # Attach duration, round to milliseconds for stability
    out: List[Dict[str, float]] = []
    for m in merged:
        s = round(float(m["start"]), 3)
        e = round(float(m["end"]), 3)
        if e <= s:
            continue
        out.append({"start": s, "end": e, "duration": round(e - s, 3)})

    return out


def generate_report(original_path: str, compressed_path: str, segments_path: Optional[str] = None) -> Dict[str, Any]:
    # Get durations from media
    original_duration = get_duration(original_path)
    compressed_duration = get_duration(compressed_path)

    removed_duration = max(0.0, float(original_duration) - float(compressed_duration))
    compression_pct = (removed_duration / original_duration) * 100 if original_duration > 0 else 0.0

    segments_removed: List[Dict[str, float]] = []
    if segments_path:
        raw = _load_segments_any(segments_path)
        segments_removed = _clamp_and_merge(raw, duration=float(original_duration), eps=EPS_DEFAULT)

    return {
        "original_duration_seconds": round(float(original_duration), 2),
        "compressed_duration_seconds": round(float(compressed_duration), 2),
        "removed_duration_seconds": round(float(removed_duration), 2),
        "compression_percentage": round(float(compression_pct), 2),
        "segments_removed": segments_removed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate compression report")
    parser.add_argument("--original", required=True, help="Path to original video")
    parser.add_argument("--compressed", required=True, help="Path to compressed video")
    parser.add_argument("--segments", help="Path to segments JSON (optional)")
    parser.add_argument("--output", required=True, help="Path to output report JSON")

    args = parser.parse_args()

    print("Generating compression report...")
    print(f"  Original: {args.original}")
    print(f"  Compressed: {args.compressed}")
    if args.segments:
        print(f"  Segments: {args.segments}")

    report = generate_report(args.original, args.compressed, args.segments)

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nOriginal: {report['original_duration_seconds']}s")
    print(f"Compressed: {report['compressed_duration_seconds']}s")
    print(f"Removed: {report['removed_duration_seconds']}s")
    print(f"Compression: {report['compression_percentage']:.2f}%")
    print(f"Segments in report: {len(report['segments_removed'])}")
    print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()
