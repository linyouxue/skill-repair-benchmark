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



    if window_seconds <= 0:
        raise ValueError("window_seconds must be greater than 0")
    # Load audio
    with wave.open(audio_path, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        audio_data = wav_file.readframes(frame_count)
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

    # Calculate RMS energy per window
    window_size = max(1, int(sample_rate * window_seconds))
    energies = []

    for i in range(0, len(audio_array), window_size):
        window = audio_array[i : i + window_size]
        if len(window) > 0:
            rms = np.sqrt(np.mean(window**2))
            energies.append(float(rms))

    total_seconds = frame_count / sample_rate if sample_rate else 0.0

    if energies:
        stats = {
            "min": float(np.min(energies)),
            "max": float(np.max(energies)),
            "mean": float(np.mean(energies)),
            "std": float(np.std(energies)),
        }
    else:
        stats = {
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "std": 0.0,
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

    print(f"\nEnergy calculated for {result['total_seconds']:.2f}s of audio")

    if result['energies']:
        print(f"Energy range: {result['stats']['min']:.1f} - {result['stats']['max']:.1f}")
        print(f"Mean energy: {result['stats']['mean']:.1f}")
    else:
        print("No audio samples detected; generated empty energy profile")

    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
