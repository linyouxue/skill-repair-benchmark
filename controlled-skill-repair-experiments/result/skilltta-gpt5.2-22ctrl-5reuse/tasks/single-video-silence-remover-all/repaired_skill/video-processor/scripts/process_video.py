#!/usr/bin/env python3
"""
Video segment processor.
Removes specified segments and concatenates remaining parts.

Contract:
- Time unit: seconds (float)
- Interval convention: half-open [start, end)
- duration = end - start

This processor defensively:
- loads segments from one or more JSON files,
- clamps to [0, video_duration],
- merges overlaps/adjacent segments (to avoid negative keep ranges),
- builds an ffmpeg filtergraph that is valid for multiple trims (uses split/asplit).
"""

import argparse
import json
import math
import subprocess
from typing import Any, Dict, List


EPS_DEFAULT = 1e-3


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds."""
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


def has_audio_stream(video_path: str) -> bool:
    """Return True if the input has at least one audio stream."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def load_segments(segment_files: List[str]) -> List[Dict[str, Any]]:
    """Load segments from one or more JSON files."""
    all_segments: List[Dict[str, Any]] = []

    for file_path in segment_files:
        with open(file_path) as f:
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
            if isinstance(seg, dict) and ("start" in seg and "end" in seg):
                all_segments.append(seg)

    # Sort by start time
    all_segments.sort(key=lambda x: float(x.get("start", 0.0)))
    return all_segments


def normalize_and_merge_remove_segments(
    remove_segments: List[Dict[str, Any]],
    *,
    total_duration: float,
    eps: float = EPS_DEFAULT,
) -> List[Dict[str, Any]]:
    """Clamp, sanitize, and merge removal segments.

    Output segments are sorted, non-overlapping, half-open, and have correct duration.
    """

    cleaned: List[Dict[str, Any]] = []

    for seg in remove_segments:
        try:
            start = float(seg.get("start"))
            end = float(seg.get("end"))
        except Exception:
            continue

        if not math.isfinite(start) or not math.isfinite(end):
            continue

        # Clamp to [0, total_duration]
        start = max(0.0, min(start, float(total_duration)))
        end = max(0.0, min(end, float(total_duration)))

        if end <= start + 1e-12:
            continue

        out = dict(seg)
        out["start"] = float(start)
        out["end"] = float(end)
        out["duration"] = float(end - start)
        cleaned.append(out)

    if not cleaned:
        return []

    cleaned.sort(key=lambda s: (s["start"], s["end"]))

    merged: List[Dict[str, Any]] = []
    cur = dict(cleaned[0])

    for seg in cleaned[1:]:
        if float(seg["start"]) <= float(cur["end"]) + float(eps):
            # overlap/adjacent -> merge
            cur["end"] = max(float(cur["end"]), float(seg["end"]))
            cur["duration"] = float(cur["end"] - cur["start"])
            # If types disagree, drop 'type' to avoid misleading.
            if "type" in cur and "type" in seg and cur.get("type") != seg.get("type"):
                cur.pop("type", None)
        else:
            merged.append(cur)
            cur = dict(seg)

    merged.append(cur)

    # Final duration recompute (defensive)
    for s in merged:
        s["duration"] = float(s["end"] - s["start"])

    return merged


def calculate_keep_segments(remove_segments: List[Dict[str, Any]], total_duration: float, eps: float = EPS_DEFAULT) -> List[Dict[str, Any]]:
    """Calculate segments to keep as the complement of removal segments over [0,total_duration)."""
    keep_segments: List[Dict[str, Any]] = []

    current = 0.0

    for seg in remove_segments:
        s0 = float(seg["start"])
        s1 = float(seg["end"])

        if current < s0 - eps:
            keep_segments.append({"start": float(current), "end": float(s0)})

        current = max(float(current), float(s1))

    if current < float(total_duration) - eps:
        keep_segments.append({"start": float(current), "end": float(total_duration)})

    # drop any tiny/invalid keep segments
    keep_segments = [s for s in keep_segments if float(s["end"]) > float(s["start"]) + 1e-9]
    return keep_segments


def _fmt_time(t: float) -> str:
    # ffmpeg accepts decimals; 3ms resolution is usually enough and stabilizes graphs
    return f"{float(t):.3f}"


def build_ffmpeg_filter(keep_segments: List[Dict[str, Any]], *, include_audio: bool) -> str:
    """Build ffmpeg filter_complex for segment processing.

    For multiple keep segments, uses split/asplit to avoid multi-consumption of input pads.
    """

    n = len(keep_segments)
    if n <= 0:
        raise ValueError("No keep segments to process")

    parts: List[str] = []

    if n == 1:
        seg = keep_segments[0]
        parts.append(
            f"[0:v]trim=start={_fmt_time(seg['start'])}:end={_fmt_time(seg['end'])},setpts=PTS-STARTPTS[outv]"
        )
        if include_audio:
            parts.append(
                f"[0:a]atrim=start={_fmt_time(seg['start'])}:end={_fmt_time(seg['end'])},asetpts=PTS-STARTPTS[outa]"
            )
        return ";".join(parts)

    # split video
    v_labels = "".join([f"[v{i}]" for i in range(n)])
    parts.append(f"[0:v]split={n}{v_labels}")

    # split audio (if present)
    if include_audio:
        a_labels = "".join([f"[a{i}]" for i in range(n)])
        parts.append(f"[0:a]asplit={n}{a_labels}")

    # per-segment trims
    for i, seg in enumerate(keep_segments):
        parts.append(
            f"[v{i}]trim=start={_fmt_time(seg['start'])}:end={_fmt_time(seg['end'])},setpts=PTS-STARTPTS[v{i}t]"
        )
        if include_audio:
            parts.append(
                f"[a{i}]atrim=start={_fmt_time(seg['start'])}:end={_fmt_time(seg['end'])},asetpts=PTS-STARTPTS[a{i}t]"
            )

    # concat
    v_inputs = "".join([f"[v{i}t]" for i in range(n)])
    parts.append(f"{v_inputs}concat=n={n}:v=1:a=0[outv]")

    if include_audio:
        a_inputs = "".join([f"[a{i}t]" for i in range(n)])
        parts.append(f"{a_inputs}concat=n={n}:v=0:a=1[outa]")

    return ";".join(parts)


def process_video(input_path: str, output_path: str, keep_segments: List[Dict[str, Any]], *, include_audio: bool):
    """Process video using ffmpeg."""

    filter_complex = build_ffmpeg_filter(keep_segments, include_audio=include_audio)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
    ]

    if include_audio:
        cmd += ["-map", "[outa]"]
    else:
        cmd += ["-an"]

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
    ]

    if include_audio:
        cmd += [
            "-c:a",
            "aac",
            "-b:a",
            "128k",
        ]

    cmd.append(output_path)

    print("Processing video...")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        stdout = e.stdout or ""
        raise RuntimeError(
            "ffmpeg failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{stdout[-4000:]}\n"
            f"stderr:\n{stderr[-4000:]}"
        ) from e


def main():
    parser = argparse.ArgumentParser(description="Process video by removing segments")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--remove-segments", nargs="+", required=True, help="JSON file(s) with segments to remove")
    parser.add_argument("--eps", type=float, default=EPS_DEFAULT, help="Merge epsilon in seconds (default: 1e-3)")

    args = parser.parse_args()

    print(f"Loading video: {args.input}")

    # Get video duration
    total_duration = get_video_duration(args.input)
    print(f"Video duration: {total_duration:.2f}s ({total_duration/60:.2f} min)")

    include_audio = has_audio_stream(args.input)
    print(f"Audio stream detected: {include_audio}")

    # Load segments to remove
    print(f"\nLoading removal segments from {len(args.remove_segments)} file(s)...")
    remove_segments_raw = load_segments(args.remove_segments)
    print(f"Loaded {len(remove_segments_raw)} raw segments to remove")

    # Normalize/merge/clamp removal segments (defensive)
    remove_segments = normalize_and_merge_remove_segments(remove_segments_raw, total_duration=total_duration, eps=args.eps)
    removed_duration = float(sum(float(s["end"]) - float(s["start"]) for s in remove_segments))

    print(f"Merged segments to remove: {len(remove_segments)}")
    print(f"Total removal (merged): {removed_duration:.2f}s ({removed_duration/60:.2f} min)")

    # Calculate segments to keep
    keep_segments = calculate_keep_segments(remove_segments, total_duration, eps=args.eps)
    print(f"Segments to keep: {len(keep_segments)}")

    if not keep_segments:
        raise RuntimeError("All content would be removed; refusing to produce an empty output.")

    # Process video
    process_video(args.input, args.output, keep_segments, include_audio=include_audio)

    # Verify output
    output_duration = get_video_duration(args.output)

    # Generate internal report (not the task-format report-generator output)
    report = {
        "original_duration": float(total_duration),
        "output_duration": float(output_duration),
        "removed_duration": float(total_duration - output_duration),
        "compression_percentage": round((total_duration - output_duration) / total_duration * 100, 2) if total_duration > 0 else 0.0,
        "segments_removed": len(remove_segments),
        "segments_kept": len(keep_segments),
    }

    report_path = args.output.replace(".mp4", "_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print("\n✓ Processing complete!")
    print(f"  Original: {total_duration:.2f}s ({total_duration/60:.2f} min)")
    print(f"  Output: {output_duration:.2f}s ({output_duration/60:.2f} min)")
    print(f"  Saved: {total_duration - output_duration:.2f}s ({(total_duration - output_duration)/60:.2f} min)")
    print(f"  Compression: {report['compression_percentage']}%")
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
