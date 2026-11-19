#!/usr/bin/env python3
"""video-processor

Remove specified segments from a video and concatenate the remaining parts.

Key properties:
- Works with multiple removal segment files.
- Validates, merges, and clips segments to video duration.
- Generates an ffmpeg filter_complex script (more robust for long filters).
- Ensures audio/video are concatenated together to preserve A/V sync.

Input segment format: JSON containing either:
- {"segments": [{"start": <number>, "end": <number>, ...}, ...]}
- A raw list of segment dicts
- A single segment dict

Only `start` and `end` are required; `duration` is ignored/recomputed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _ffprobe_duration_seconds(video_path: str) -> float:
    """Get media duration in seconds using ffprobe."""
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
    data: Any = json.loads(Path(path).read_text(encoding="utf-8"))

    if isinstance(data, dict) and "segments" in data:
        segs = data.get("segments")
    elif isinstance(data, list):
        segs = data
    elif isinstance(data, dict):
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


def _normalize_remove_segments(
    raw_segments: List[Dict[str, Any]],
    *,
    duration_seconds: float,
    merge_gap: float = 0.05,
    min_duration: float = 0.001,
) -> List[Tuple[float, float]]:
    """Coerce, clip, merge, and filter removal segments."""
    dur = max(0.0, float(duration_seconds))
    merge_gap = max(0.0, float(merge_gap))
    min_duration = max(0.0, float(min_duration))

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
        # Clip to [0, dur]
        s = max(0.0, s)
        e = min(dur, e)
        if e > s:
            pairs.append((s, e))

    if not pairs:
        return []

    pairs.sort(key=lambda x: (x[0], x[1]))

    merged: List[List[float]] = [[pairs[0][0], pairs[0][1]]]
    for s, e in pairs[1:]:
        ps, pe = merged[-1]
        if s <= pe + merge_gap:
            merged[-1][1] = max(pe, e)
        else:
            merged.append([s, e])

    out: List[Tuple[float, float]] = []
    for s, e in merged:
        if e - s >= min_duration:
            out.append((float(s), float(e)))

    return out


def _invert_segments(remove_segments: List[Tuple[float, float]], duration_seconds: float) -> List[Tuple[float, float]]:
    """Compute keep segments as the inverse of remove segments."""
    dur = max(0.0, float(duration_seconds))
    if dur <= 0:
        return []

    if not remove_segments:
        return [(0.0, dur)]

    keep: List[Tuple[float, float]] = []
    cursor = 0.0
    for s, e in remove_segments:
        if s > cursor:
            keep.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < dur:
        keep.append((cursor, dur))

    # Drop ultra-short keeps that can cause concat issues.
    keep = [(s, e) for s, e in keep if (e - s) > 0.01]
    return keep


def _build_filter_script(keep_segments: List[Tuple[float, float]]) -> str:
    """Build an ffmpeg filter_complex script that trims & concatenates A/V together."""
    lines: List[str] = []

    for i, (s, e) in enumerate(keep_segments):
        lines.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
        lines.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")

    if len(keep_segments) == 1:
        # No concat needed; still produce consistent labels.
        # Use null/anull (widely available) to relabel streams.
        lines.append("[v0]null[outv]")
        lines.append("[a0]anull[outa]")
    else:
        # Concatenate audio and video together to guarantee alignment.
        inputs = "".join(f"[v{i}][a{i}]" for i in range(len(keep_segments)))
        lines.append(f"{inputs}concat=n={len(keep_segments)}:v=1:a=1[outv][outa]")

    return ";\n".join(lines) + "\n"


def process_video(
    input_path: str,
    output_path: str,
    remove_segments: List[Tuple[float, float]],
    *,
    preset: str = "veryfast",
    crf: int = 23,
    audio_bitrate: str = "128k",
) -> None:
    """Process video using ffmpeg."""

    duration = _ffprobe_duration_seconds(input_path)
    keep_segments = _invert_segments(remove_segments, duration)

    if not keep_segments:
        raise RuntimeError("No keep segments remain after applying removals; refusing to create empty output")

    # Use a filter script file to avoid shell escaping issues and filter length limits.
    tmp_dir = Path("work")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    filter_path = tmp_dir / "filter_complex.txt"
    filter_path.write_text(_build_filter_script(keep_segments), encoding="utf-8")

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_path,
        "-filter_complex_script",
        str(filter_path),
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        str(preset),
        "-crf",
        str(int(crf)),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        str(audio_bitrate),
        "-movflags",
        "+faststart",
        output_path,
    ]

    print("Processing video...")
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process video by removing segments")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--remove-segments", nargs="+", required=True, help="JSON file(s) with segments to remove")
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.0,
        help="Merge removal segments separated by <= this many seconds (default: 0.0)",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.0,
        help="Drop removal segments shorter than this many seconds (default: 0.0)",
    )
    parser.add_argument("--preset", default="veryfast", help="x264 preset (default: veryfast)")
    parser.add_argument("--crf", type=int, default=23, help="x264 CRF quality (default: 23)")
    parser.add_argument("--audio-bitrate", default="128k", help="AAC bitrate (default: 128k)")

    args = parser.parse_args()

    input_path = args.input
    output_path = args.output

    print(f"Loading video: {input_path}")
    duration = _ffprobe_duration_seconds(input_path)
    print(f"Video duration: {duration:.3f}s ({duration/60:.2f} min)")

    print(f"\nLoading removal segments from {len(args.remove_segments)} file(s)...")
    raw: List[Dict[str, Any]] = []
    for p in args.remove_segments:
        raw.extend(_load_segments_from_json(p))

    remove_pairs = _normalize_remove_segments(
        raw,
        duration_seconds=duration,
        merge_gap=args.merge_gap,
        min_duration=args.min_duration,
    )

    removed_duration = sum(e - s for s, e in remove_pairs)
    print(f"Loaded {len(remove_pairs)} removal segments")
    print(f"Total removal (after merge/clip): {removed_duration:.3f}s ({removed_duration/60:.2f} min)")

    process_video(
        input_path,
        output_path,
        remove_pairs,
        preset=args.preset,
        crf=args.crf,
        audio_bitrate=args.audio_bitrate,
    )

    # Verify output
    out_duration = _ffprobe_duration_seconds(output_path)

    report = {
        "original_duration": round(duration, 3),
        "output_duration": round(out_duration, 3),
        "removed_duration": round(max(0.0, duration - out_duration), 3),
        "compression_percentage": round(((duration - out_duration) / duration) * 100.0, 3) if duration else 0.0,
        "segments_removed": len(remove_pairs),
    }

    report_path = Path(output_path).with_suffix("")
    report_path = report_path.with_name(report_path.name + "_report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n✓ Processing complete!")
    print(f"  Original: {report['original_duration']}s")
    print(f"  Output:   {report['output_duration']}s")
    print(f"  Removed:  {report['removed_duration']}s")
    print(f"  Compression: {report['compression_percentage']}%")
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
