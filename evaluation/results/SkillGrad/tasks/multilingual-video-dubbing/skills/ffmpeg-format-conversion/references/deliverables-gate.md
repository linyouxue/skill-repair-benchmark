# Deliverables gate for file-based graders

Use this procedure when the task is evaluated by presence of files at exact paths (e.g., `/outputs/...`). The goal is to **block termination** until artifacts exist, are readable, and match minimal format expectations.

## Procedure

### 1) Define the deliverables set (exact paths)

Create a single source of truth (list or dict) of required paths.

```python
from pathlib import Path

def required_paths():
    return [
        Path("/outputs/tts_segments/seg_0.wav"),
        Path("/outputs/dubbed.mp4"),
        Path("/outputs/report.json"),
    ]
```

### 2) Ensure directories exist

```python
from pathlib import Path

for p in required_paths():
    p.parent.mkdir(parents=True, exist_ok=True)
```

### 3) Branch: verify existence vs. create missing artifacts

```python
from pathlib import Path

missing = [p for p in required_paths() if not p.exists()]
if missing:
    print("Missing deliverables:")
    for p in missing:
        print("-", p)
    # Corrective action: return to the pipeline step that produces each file.
    # Do NOT proceed to final submission.
else:
    print("All deliverables exist; proceed to readability/metadata checks.")
```

### 4) Readability + minimal metadata checks (runnable)

This step catches empty/corrupted files and common container mistakes.

```python
import json
import subprocess
from pathlib import Path

wav = Path("/outputs/tts_segments/seg_0.wav")
mp4 = Path("/outputs/dubbed.mp4")
report = Path("/outputs/report.json")

# JSON parses
with report.open("r", encoding="utf-8") as f:
    data = json.load(f)

# ffprobe exits 0
subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", str(wav)], check=True)
subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", str(mp4)], check=True)

print("readability: ok")
```

### 5) Runtime branch: inspect streams and correct

Use `ffprobe` JSON to assert the container has the expected stream types.

```python
import json
import subprocess
from pathlib import Path

mp4 = Path("/outputs/dubbed.mp4")
probe = subprocess.run(
    ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(mp4)],
    check=True,
    capture_output=True,
    text=True,
)
info = json.loads(probe.stdout)
codec_types = [s.get("codec_type") for s in info.get("streams", [])]

if "video" not in codec_types or "audio" not in codec_types:
    print("dubbed.mp4 missing expected streams:", codec_types)
    # Corrective action: re-mux ensuring explicit mapping, e.g. map one video + one audio.
else:
    print("streams: ok", codec_types)
```

## Verification (do not skip)

1) Re-run the existence check: if any path is missing, **go back and generate that artifact**.

2) Re-run readability checks:
- If `ffprobe` fails on WAV: re-export the segment (set explicit `-ar`/`-ac`, avoid `-c copy`).
- If `ffprobe` fails or streams are missing on MP4: re-mux with explicit stream mapping.
- If JSON fails to parse: rewrite the file and re-parse.

Only terminate after all checks pass.
