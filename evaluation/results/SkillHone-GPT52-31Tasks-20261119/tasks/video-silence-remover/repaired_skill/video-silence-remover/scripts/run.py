#!/usr/bin/env python3
"""video-silence-remover


End-to-end runner that:
- Extracts audio from an input video
- Computes windowed RMS energies
- Detects an initial opening segment
- Detects long pauses
- Combines/normalizes removal segments
- Cuts the video
- Generates a task-format compression report

This is intentionally a thin orchestrator that shells out to the other skill
scripts, so each component can also be used independently.

IMPORTANT: This script should not embed instance-specific answers; it only wires
the reusable pipeline.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def _run(cmd: List[str]) -> None:
    """Run a subprocess command with a helpful error on failure."""

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Required tool not found while running: {cmd[0]!r}. "
            "Ensure ffmpeg/ffprobe and python are available on PATH."
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed (exit {e.returncode}): {' '.join(cmd)}") from e


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove opening and pauses from a teaching video")
    parser.add_argument("--input-video", required=True, help="Path to input video")
    parser.add_argument("--output-video", default="compressed_video.mp4", help="Output video path")
    parser.add_argument("--report", default="compression_report.json", help="Output report path")

    # Intermediate artifacts
    parser.add_argument("--workdir", default="work", help="Directory for intermediate files")

    # Energy calculation
    parser.add_argument("--window-seconds", type=float, default=0.5, help="Energy window size in seconds")

    # Opening detection
    parser.add_argument("--opening-search-max", type=float, default=120.0, help="Max seconds from start to search")
    parser.add_argument("--opening-baseline-seconds", type=float, default=30.0, help="Seconds used for baseline")
    parser.add_argument("--opening-threshold-multiplier", type=float, default=2.0, help="Opening threshold multiplier")
    parser.add_argument("--opening-sustain-seconds", type=float, default=2.0, help="Seconds above threshold required")

    # Pause detection
    parser.add_argument("--min-pause-seconds", type=float, default=2.0, help="Minimum pause duration to remove")
    parser.add_argument("--pause-window-size", type=float, default=30.0, help="Local baseline window in seconds")
    parser.add_argument("--pause-threshold-ratio", type=float, default=0.5, help="Local threshold ratio")
    parser.add_argument("--pause-merge-gap", type=float, default=0.0, help="Merge pauses separated by <= gap seconds")
    parser.add_argument(
        "--pause-smoothing-seconds",
        type=float,
        default=1.0,
        help="Smooth energies over this many seconds before pause detection (default: 1.0)",
    )
    parser.add_argument(
        "--pause-require-absolute-gate",
        action="store_true",
        help="Require absolute noise-floor gate in pause detection (more conservative)",
    )

    # Segment combination
    parser.add_argument("--segments-merge-gap", type=float, default=0.0, help="Merge removal segments separated by <= gap seconds")
    parser.add_argument("--segments-min-duration", type=float, default=0.0, help="Drop removal segments shorter than this")

    # Video processing
    parser.add_argument("--preset", default="veryfast", help="x264 preset")
    parser.add_argument("--crf", type=int, default=23, help="x264 CRF")
    parser.add_argument("--audio-bitrate", default="128k", help="AAC bitrate")

    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    input_video = Path(args.input_video)
    output_video = Path(args.output_video)
    report_path = Path(args.report)

    audio_wav = workdir / "audio.wav"
    energies_json = workdir / "energies.json"
    opening_json = workdir / "opening.json"
    pauses_json = workdir / "pauses.json"
    combined_json = workdir / "segments_removed.json"

    # 1) Extract analysis audio
    _run(
        [
            sys.executable,
            "skills/audio-extractor/scripts/extract_audio.py",
            "--video",
            str(input_video),
            "--output",
            str(audio_wav),
            "--sample-rate",
            "16000",
        ]
    )

    # 2) Compute energies
    _run(
        [
            sys.executable,
            "skills/energy-calculator/scripts/calc_energy.py",
            "--audio",
            str(audio_wav),
            "--output",
            str(energies_json),
            "--window-seconds",
            str(float(args.window_seconds)),
        ]
    )

    # 3) Detect opening
    _run(
        [
            sys.executable,
            "skills/silence-detector/scripts/detect_silence.py",
            "--energies",
            str(energies_json),
            "--output",
            str(opening_json),
            "--search-max",
            str(float(args.opening_search_max)),
            "--baseline-seconds",
            str(float(args.opening_baseline_seconds)),
            "--threshold-multiplier",
            str(float(args.opening_threshold_multiplier)),
            "--sustain-seconds",
            str(float(args.opening_sustain_seconds)),
        ]
    )

    opening_data = _load_json(opening_json)
    opening_end = 0.0
    if isinstance(opening_data, dict):
        segs = opening_data.get("segments")
        if isinstance(segs, list) and segs:
            try:
                opening_end = float(segs[0].get("end", 0.0))
            except (TypeError, ValueError):
                opening_end = 0.0

    # 4) Detect pauses (skip opening)
    pause_cmd = [
        sys.executable,
        "skills/pause-detector/scripts/detect_pauses.py",
        "--energies",
        str(energies_json),
        "--output",
        str(pauses_json),
        "--start-time",
        str(float(opening_end)),
        "--min-duration",
        str(float(args.min_pause_seconds)),
        "--window-size",
        str(float(args.pause_window_size)),
        "--threshold-ratio",
        str(float(args.pause_threshold_ratio)),
        "--merge-gap",
        str(float(args.pause_merge_gap)),
        "--smoothing-seconds",
        str(float(args.pause_smoothing_seconds)),
    ]
    if bool(args.pause_require_absolute_gate):
        pause_cmd.append("--no-allow-local-only")

    _run(pause_cmd)

    # 5) Combine segments
    _run(
        [
            sys.executable,
            "skills/segment-combiner/scripts/combine_segments.py",
            "--segments",
            str(opening_json),
            str(pauses_json),
            "--output",
            str(combined_json),
            "--merge-gap",
            str(float(args.segments_merge_gap)),
            "--min-duration",
            str(float(args.segments_min_duration)),
        ]
    )

    # 6) Process video
    _run(
        [
            sys.executable,
            "skills/video-processor/scripts/process_video.py",
            "--input",
            str(input_video),
            "--output",
            str(output_video),
            "--remove-segments",
            str(combined_json),
            "--merge-gap",
            "0.0",
            "--min-duration",
            "0.0",
            "--preset",
            str(args.preset),
            "--crf",
            str(int(args.crf)),
            "--audio-bitrate",
            str(args.audio_bitrate),
        ]
    )

    # 7) Generate task-format report
    _run(
        [
            sys.executable,
            "skills/report-generator/scripts/generate_report.py",
            "--original",
            str(input_video),
            "--compressed",
            str(output_video),
            "--segments",
            str(combined_json),
            "--output",
            str(report_path),
            "--merge-gap",
            "0.0",
            "--min-duration",
            "0.0",
            "--round-ndigits",
            "3",
        ]
    )

    print("\n✓ Done")
    print(f"  Output video: {output_video}")
    print(f"  Report:       {report_path}")
    print(f"  Segments:     {combined_json}")


if __name__ == "__main__":
    main()
