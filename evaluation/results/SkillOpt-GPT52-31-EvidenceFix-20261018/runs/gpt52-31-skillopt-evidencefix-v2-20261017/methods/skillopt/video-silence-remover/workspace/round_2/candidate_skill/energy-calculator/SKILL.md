---
name: energy-calculator
description: Calculate per-second RMS energy from audio files. Use when you need to analyze audio volume patterns, prepare data for silence/pause detection, or create an energy profile for audio analysis tasks.
---

# Energy Calculator

Calculates per-second RMS (Root Mean Square) energy from audio files. Produces an energy profile that can be used for opening detection, pause detection, or other audio analysis tasks.

## Use Cases

- Calculating audio energy for silence detection
- Preparing data for opening/pause detection
- Analyzing audio volume patterns

## Usage

```bash
python3 /root/.claude/skills/energy-calculator/scripts/calc_energy.py \
    --audio /path/to/audio.wav \
    --output /path/to/energies.json
```

### Parameters

- `--audio`: Path to input WAV file
- `--output`: Path to output JSON file
- `--window-seconds`: Window size for energy calculation (default: 1 second)


  - Recommended values:
    - `1.0`: Stable coarse analysis for long-form loudness trends.
    - `0.25-0.5`: Better for pause/opening detection where pauses may only last 2-5 seconds.
  - Smaller windows increase timestamp precision and typically improve downstream pause-detector recall and segment IoU, but may require stronger smoothing or merging of nearby detections.
### Output Format

```json
{
  "sample_rate": 16000,
  "window_seconds": 1,
  "total_seconds": 600,
  "energies": [123.5, 456.7, 234.2, ...],
  "stats": {
    "min": 45.2,
    "max": 892.3,
    "mean": 234.5,
    "std": 156.7
  }
}
```

## How It Works

1. Load audio file
2. Split into 1-second windows
3. Calculate RMS energy for each window: `sqrt(mean(samples^2))`

Window size directly affects temporal precision:
- Larger windows (for example `1.0s`) produce smoother energy curves with less noise, but short pauses can be blurred together or shifted at boundaries.
- Smaller windows (for example `0.25-0.5s`) improve pause sensitivity and boundary alignment for short 2-5s pauses, because detectors receive higher-resolution energy changes.
- Higher-resolution energy can increase false positives from brief quiet words, breaths, or background fluctuations, so downstream detectors may need smoothing, hysteresis, or segment merging.

4. Output array of energy values

## Dependencies

- Python 3.11+
- numpy

## Example

```bash
# Calculate energy from extracted audio
python3 /root/.claude/skills/energy-calculator/scripts/calc_energy.py \
    --audio audio.wav \
    --output energies.json
```


### Higher-resolution example for pause detection

For lecture or teaching videos with short pauses, use sub-second windows:

```bash
python3 /root/.claude/skills/energy-calculator/scripts/calc_energy.py \
    --audio audio.wav \
    --window-seconds 0.25 \
    --output energies.json
```

This produces 4 energy samples per second, which helps downstream detectors:
- detect brief 2-5s pauses more reliably
- place cut boundaries closer to actual silence transitions
- reduce under-segmentation where speech and silence share the same 1s bucket

When using smaller windows, downstream pause detectors should usually merge adjacent low-energy spans separated by very short gaps (for example <0.5-1.0s).
## Notes

- RMS energy correlates with perceived loudness
- Higher values = louder audio, lower values = quieter/silence
- Output can be used by opening-detector and pause-detector skills
- `window_seconds` should match the detection goal:
  - `1.0s` windows are usually sufficient for broad opening detection.
  - `0.25-0.5s` windows are typically better for precise silence trimming and short-pause removal.
- Higher-resolution energy often improves downstream recall and boundary IoU for pause detection, but detectors may need smoothing, rolling averages, or post-processing merges to avoid noisy micro-segments.
