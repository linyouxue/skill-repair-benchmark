#!/usr/bin/env python3
"""
Energy calculator - calculates per-second RMS energy from audio.
"""

import argparse
import json
import wave

import numpy as np


def calculate_energy(audio_path, window_seconds=1):
    """Calculate per-second RMS energy from audio file."""

    # Load audio
    with wave.open(audio_path, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        audio_data = wav_file.readframes(wav_file.getnframes())
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

    # Calculate RMS energy per window
    window_size = int(sample_rate * window_seconds)
    energies = []


    # Total duration in seconds based on sample count (more accurate than len(energies)*window_seconds)
    total_seconds = (len(audio_array) / sample_rate) if sample_rate else 0.0

    # Guard: empty audio (or unreadable frames)
    if len(audio_array) == 0 or window_size <= 0:
        return {
            "sample_rate": sample_rate,
            "window_seconds": window_seconds,
            "total_seconds": float(total_seconds),
            "energies": [],
            "stats": {"min": None, "max": None, "mean": None, "std": None},
        }
    for i in range(0, len(audio_array), window_size):
        window = audio_array[i : i + window_size]
        if len(window) > 0:
            rms = np.sqrt(np.mean(window**2))
            energies.append(float(rms))

    if len(energies) == 0:
        stats = {"min": None, "max": None, "mean": None, "std": None}
    else:
        stats = {
            "min": float(np.min(energies)),
            "max": float(np.max(energies)),
            "mean": float(np.mean(energies)),
            "std": float(np.std(energies)),
        }

    return {
        "sample_rate": sample_rate,
        "window_seconds": window_seconds,
        "total_seconds": float(total_seconds),
        "energies": energies,
        "stats": stats,
    }


def main():
    parser = argparse.ArgumentParser(description="Calculate per-second RMS energy from audio")
    parser.add_argument("--audio", required=True, help="Path to input WAV file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--window-seconds", type=float, default=1, help="Window size in seconds (default: 1)")

    args = parser.parse_args()

    print(f"Calculating energy from: {args.audio}")
    print(f"Window size: {args.window_seconds}s")

    result = calculate_energy(args.audio, args.window_seconds)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nEnergy calculated for {result['total_seconds']:.3f}s of audio")
    if result.get("energies"):
        print(f"Energy range: {result['stats']['min']:.1f} - {result['stats']['max']:.1f}")
        print(f"Mean energy: {result['stats']['mean']:.1f}")
    else:
        print("No energy windows produced (empty/too-short audio).")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
