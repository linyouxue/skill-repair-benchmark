#!/usr/bin/env python3
"""
Video segment processor.
Removes specified segments and concatenates remaining parts.

Hardening fixes:
- Normalizes/clamps/merges remove segments to avoid overlap bugs.
- Keeps cursor monotonic when computing keep segments.
- Does not trust input `duration`; recomputes as end-start.
- Fixes ffmpeg argument ordering (-y before outputs).
- Handles empty/degenerate keep/remove segments safely.

Interval convention: half-open [start, end) in seconds.
"""

import argparse
import json
import subprocess
from typing import Any, Dict, Iterable, List, Optional


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
            "csv=p=0",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


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


def load_segments(segment_files: List[str]) -> List[Dict[str, Any]]:
    """Load segments from one or more JSON files."""
    all_segments: List[Dict[str, Any]] = []

    for file_path in segment_files:
        with open(file_path) as f:
            data = json.load(f)
        all_segments.extend(list(_iter_segments_from_json(data)))

    return all_segments


def normalize_segments(segments: List[Dict[str, Any]], total_duration: float) -> List[Dict[str, Any]]:
    """Clamp segments to [0,total_duration], drop invalid, recompute duration."""

    out: List[Dict[str, Any]] = []
    T = float(total_duration)

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


def merge_segments(segments: List[Dict[str, Any]], merge_gap: float = 0.1) -> List[Dict[str, Any]]:
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

            # Preserve consistent type if present.
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


def calculate_keep_segments(remove_segments: List[Dict[str, Any]], total_duration: float, min_keep_duration: float = 0.001) -> List[Dict[str, float]]:
    """Calculate segments to keep (inverse of remove segments)."""

    keep_segments: List[Dict[str, float]] = []
    cursor = 0.0
    T = float(total_duration)
    min_keep = max(0.0, float(min_keep_duration))

    for seg in remove_segments:
        s = float(seg["start"])
        e = float(seg["end"])

        # Only add a keep segment if it has meaningful duration.
        if s > cursor + min_keep:
            keep_segments.append({"start": cursor, "end": s})

        # Cursor must never move backwards.
        cursor = max(cursor, e)

    if T > cursor + min_keep:
        keep_segments.append({"start": cursor, "end": T})

    # Filter any numerical noise
    keep_segments = [k for k in keep_segments if k["end"] > k["start"] + min_keep]
    return keep_segments


def build_ffmpeg_filter(keep_segments: List[Dict[str, float]], include_audio: bool) -> str:
    """Build ffmpeg filter_complex for segment processing."""

    filter_parts: List[str] = []

    for i, seg in enumerate(keep_segments):
        s = seg["start"]
        e = seg["end"]
        filter_parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
        if include_audio:
            filter_parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")

    v_inputs = "".join([f"[v{i}]" for i in range(len(keep_segments))])
    filter_parts.append(f"{v_inputs}concat=n={len(keep_segments)}:v=1:a=0[outv]")

    if include_audio:
        a_inputs = "".join([f"[a{i}]" for i in range(len(keep_segments))])
        filter_parts.append(f"{a_inputs}concat=n={len(keep_segments)}:v=0:a=1[outa]")

    return ";".join(filter_parts)


def remux_copy(input_path: str, output_path: str) -> None:
    """Fast-path: remux/stream-copy without filtering."""
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        input_path,
        "-map",
        "0",
        "-c",
        "copy",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def process_video(input_path: str, output_path: str, keep_segments: List[Dict[str, float]], include_audio: bool) -> None:
    """Process video using ffmpeg."""

    # If we're keeping the whole video, just stream-copy.
    if len(keep_segments) == 1:
        s0 = float(keep_segments[0]["start"])
        e0 = float(keep_segments[0]["end"])
        if abs(s0 - 0.0) <= 1e-6 and e0 > 0 and abs((e0 - get_video_duration(input_path))) <= 0.05:
            remux_copy(input_path, output_path)
            return

    filter_complex = build_ffmpeg_filter(keep_segments, include_audio=include_audio)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        input_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
    ]

    if include_audio:
        cmd.extend(["-map", "[outa]"])

    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
        ]
    )

    if include_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])

    cmd.append(output_path)

    print("Processing video (this may take 10-20 minutes)...")
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description="Process video by removing segments")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--remove-segments", nargs="+", required=True, help="JSON file(s) with segments to remove")
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.1,
        help="Merge removal segments if next.start <= current.end + merge_gap (seconds). Default: 0.1",
    )
    parser.add_argument(
        "--min-keep-duration",
        type=float,
        default=0.001,
        help="Drop keep segments shorter than this (seconds). Default: 0.001",
    )

    args = parser.parse_args()

    print(f"Loading video: {args.input}")

    # Get video duration
    total_duration = get_video_duration(args.input)
    print(f"Video duration: {total_duration:.2f}s ({total_duration/60:.2f} min)")

    include_audio = has_audio_stream(args.input)
    if not include_audio:
        print("Warning: No audio stream detected; output will be video-only.")

    # Load segments to remove
    print(f"\nLoading removal segments from {len(args.remove_segments)} file(s)...")
    remove_segments_raw = load_segments(args.remove_segments)
    print(f"Loaded {len(remove_segments_raw)} raw segments")

    # Normalize + merge to avoid overlap/ordering bugs.
    remove_segments_norm = normalize_segments(remove_segments_raw, total_duration=total_duration)
    remove_segments = merge_segments(remove_segments_norm, merge_gap=args.merge_gap)
    print(f"Normalized/merged to {len(remove_segments)} segments")

    removed_duration = sum(float(s["end"]) - float(s["start"]) for s in remove_segments)
    print(f"Total removal: {removed_duration:.2f}s ({removed_duration/60:.2f} min)")

    # Calculate segments to keep
    keep_segments = calculate_keep_segments(remove_segments, total_duration, min_keep_duration=args.min_keep_duration)
    print(f"Segments to keep: {len(keep_segments)}")

    # Safety: if keep becomes empty, fall back to keeping the full input.
    if not keep_segments:
        print("Warning: keep_segments is empty after processing; falling back to full-video remux.")
        keep_segments = [{"start": 0.0, "end": total_duration}]

    # Process video
    process_video(args.input, args.output, keep_segments, include_audio=include_audio)

    # Verify output
    output_duration = get_video_duration(args.output)

    # Generate lightweight report (internal; task report is generated by report-generator).
    report = {
        "original_duration": total_duration,
        "output_duration": output_duration,
        "removed_duration": max(0.0, total_duration - output_duration),
        "compression_percentage": round((max(0.0, total_duration - output_duration) / total_duration * 100) if total_duration > 0 else 0.0, 2),
        "segments_removed": len(remove_segments),
        "segments_kept": len(keep_segments),
        "parameters": {
            "merge_gap": args.merge_gap,
            "min_keep_duration": args.min_keep_duration,
            "interval_convention": "half-open [start,end)",
        },
    }

    report_path = args.output.replace(".mp4", "_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print("\n✓ Processing complete!")
    print(f"  Original: {total_duration:.2f}s ({total_duration/60:.2f} min)")
    print(f"  Output: {output_duration:.2f}s ({output_duration/60:.2f} min)")
    print(f"  Saved: {max(0.0, total_duration - output_duration):.2f}s ({max(0.0, total_duration - output_duration)/60:.2f} min)")
    print(f"  Compression: {report['compression_percentage']}%")
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
