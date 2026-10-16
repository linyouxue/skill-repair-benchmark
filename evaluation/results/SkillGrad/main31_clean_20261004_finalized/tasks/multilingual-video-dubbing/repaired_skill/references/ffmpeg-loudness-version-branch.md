# FFmpeg loudness measurement/normalization (version-branching)

Use this when you must **hit a LUFS target** and **report measured LUFS/TP**, but you don’t know what FFmpeg build/features are available.

## 1) Detect filter capabilities

Run one of these and inspect the output:

```bash
ffmpeg -hide_banner -h filter=loudnorm | sed -n '1,120p'
ffmpeg -hide_banner -filters | grep -i loudnorm || true
```

Runtime branch:
- **If help text mentions JSON/two-pass fields** (e.g., `print_format`, `measure_only`, or documents measured_* fields), you can attempt a true two-pass loudnorm.
- **If not**, do not attempt to parse JSON from stderr; fall back to `ebur128` measurement + one-pass loudnorm (or gain-based normalization).

## 2A) Branch A — two-pass loudnorm (when supported)

```bash
# Pass 1: measurement (writes JSON-ish stats to stderr)
ffmpeg -i input.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11:print_format=json" -f null - 2> loudnorm_pass1.log

# Pass 2: apply (fill in measured_* values from pass1 log)
# NOTE: parse the log outside ffmpeg; then substitute values into loudnorm options.
ffmpeg -i input.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11" output_norm.wav
```

## 2B) Branch B — compatible fallback (always available)

```bash
# Measure integrated loudness and true peak
ffmpeg -i input.wav -af "ebur128=peak=true" -f null - 2> ebur128_before.log

# Normalize without claiming measured_* fields
ffmpeg -i input.wav -af "loudnorm=I=-23:TP=-1.5:LRA=11" output_norm.wav

# Re-measure the final audio (authoritative)
ffmpeg -i output_norm.wav -af "ebur128=peak=true" -f null - 2> ebur128_after.log
```

## 3) Verification + corrective action

Verification:
- Parse `ebur128_after.log` and confirm the reported **Integrated loudness** is within your tolerance of the target.

If verification fails:
1. Ensure you measured the **same file** you will deliver.
2. If you changed tempo/padding after normalization, move normalization to the end and rerun.
3. If the target is still missed, switch to a gain-based approach: compute gain from the `ebur128_before.log` integrated loudness, apply `volume=XdB`, then re-measure.

```python
import re, pathlib

def parse_integrated_lufs(log_text: str):
    m = re.search(r"Integrated loudness:\s+(-?\d+\.\d+) LUFS", log_text)
    return float(m.group(1)) if m else None

log = pathlib.Path("ebur128_after.log").read_text(errors="ignore")
lufs = parse_integrated_lufs(log)
assert lufs is not None, "Could not parse LUFS; rerun ebur128 with -hide_banner and capture stderr"
print("measured_lufs", lufs)

# Corrective next step (example): if too loud, reduce gain and re-measure
if lufs > -22.5:
    print("Too loud; apply negative gain and re-measure")
elif lufs < -23.5:
    print("Too quiet; apply positive gain and re-measure")
else:
    print("Within tolerance")
```
