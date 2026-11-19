#!/usr/bin/env python3
"""energy-calculator

Compute RMS energy over fixed windows from a WAV file.

This script intentionally avoids third-party Python dependencies so it can run in
minimal environments. It is compatible with WAV files produced by the
`audio-extractor` skill (mono, 16 kHz, PCM).

Output JSON format is consumed by downstream skills (silence-detector,
pause-detector).
"""

from __future__ import annotations

import argparse
import json
import statistics
import wave
from typing import Any, Dict, List

# `audioop` is in the Python stdlib (deprecated in 3.13, but available in 3.12).
import audioop


def _to_mono(frames: bytes, sample_width: int, channels: int) -> bytes:
    """Convert frames to mono when possible.

    - If already mono, returns frames unchanged.
    - If stereo (2 channels), averages L/R into mono.
    - For other channel counts, returns frames unchanged.

    This keeps the skill robust without pulling in external audio libraries.
    """

    if channels == 1:
        return frames
    if channels == 2:
        # Average left and right channels.
        return audioop.tomono(frames, sample_width, 0.5, 0.5)
    return frames


def calculate_energy(audio_path: str, window_seconds: float = 1.0) -> Dict[str, Any]:
    """Calculate RMS energy for each `window_seconds` chunk of audio."""

    if window_seconds <= 0:
        raise ValueError("window_seconds must be > 0")

    with wave.open(audio_path, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        total_frames = wav_file.getnframes()

        frames_per_window = max(1, int(round(sample_rate * window_seconds)))

        energies: List[float] = []
        frames_read = 0

        while frames_read < total_frames:
            frames = wav_file.readframes(frames_per_window)
            if not frames:
                break

            # Track progress conservatively; readframes may return fewer frames at EOF.
            frames_read = min(total_frames, frames_read + frames_per_window)

            mono = _to_mono(frames, sample_width, channels)
            # audioop.rms returns an int RMS amplitude.
            rms = float(audioop.rms(mono, sample_width))
            energies.append(rms)

    audio_duration_seconds = total_frames / float(sample_rate) if sample_rate else 0.0
    # Preserve the historical key name `total_seconds` used by downstream skills.
    total_seconds = len(energies) * float(window_seconds)

    if energies:
        mean = statistics.mean(energies)
        std = statistics.pstdev(energies) if len(energies) > 1 else 0.0
        stats = {
            "min": float(min(energies)),
            "max": float(max(energies)),
            "mean": float(mean),
            "std": float(std),
        }
    else:
        stats = {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0}

    return {
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "window_seconds": float(window_seconds),
        "audio_duration_seconds": float(audio_duration_seconds),
        "total_seconds": float(total_seconds),
        "total_windows": len(energies),
        "energies": energies,
        "stats": stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate RMS energy from WAV audio")
    parser.add_argument("--audio", required=True, help="Path to input WAV file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=1.0,
        help="Window size in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    print(f"Calculating energy from: {args.audio}")
    print(f"Window size: {args.window_seconds}s")

    result = calculate_energy(args.audio, args.window_seconds)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nEnergy calculated for ~{result['total_seconds']:.2f}s of audio")
    print(f"Energy range: {result['stats']['min']:.1f} - {result['stats']['max']:.1f}")
    print(f"Mean energy: {result['stats']['mean']:.1f}")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
