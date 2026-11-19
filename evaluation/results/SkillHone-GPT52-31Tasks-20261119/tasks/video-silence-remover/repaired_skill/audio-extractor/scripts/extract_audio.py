#!/usr/bin/env python3
"""audio-extractor

Extract audio from a video file to a WAV file suitable for downstream analysis.

Design goals:
- Use only ffmpeg (no Python audio deps)
- Produce mono 16-bit PCM WAV by default
- Be safe to call from automation (create output dirs, overwrite output)
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Optional


def extract_audio(video_path: str, output_path: str, sample_rate: int = 16000, duration: Optional[float] = None) -> str:
    """Extract audio from `video_path` to `output_path`.

    Args:
        video_path: Input video path.
        output_path: Output WAV path.
        sample_rate: Sample rate in Hz.
        duration: Optional duration limit in seconds.

    Returns:
        The output path.
    """

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",  # overwrite
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        video_path,
        "-vn",  # drop video
        "-ac",
        "1",  # mono
        "-ar",
        str(int(sample_rate)),
        "-c:a",
        "pcm_s16le",  # 16-bit PCM
    ]

    if duration is not None:
        cmd.extend(["-t", str(float(duration))])

    cmd.append(str(out_path))

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            "ffmpeg failed to extract audio. "
            "Check that ffmpeg is installed and the input video is readable."
        ) from e

    return str(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract mono PCM WAV audio from a video")
    parser.add_argument("--video", required=True, help="Path to input video")
    parser.add_argument("--output", required=True, help="Path to output WAV file")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Sample rate in Hz (default: 16000)")
    parser.add_argument("--duration", type=float, default=None, help="Optional duration limit in seconds")

    args = parser.parse_args()

    print(f"Extracting audio from: {args.video}")
    print(f"Sample rate: {args.sample_rate} Hz")
    if args.duration is not None:
        print(f"Duration limit: {args.duration}s")

    out = extract_audio(args.video, args.output, sample_rate=args.sample_rate, duration=args.duration)

    size_mb = os.path.getsize(out) / (1024 * 1024)
    print(f"\nAudio extracted to: {out}")
    print(f"File size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
