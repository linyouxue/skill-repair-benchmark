# Opening-cut verification (extreme or uncertain openings)

Use this when an opening detector proposes removing a long segment starting at t=0 (e.g., >30–60s) or when you suspect quiet speech could be misclassified as silence.

## Goal

Decide whether the proposed opening cut is safe **before** writing `remove_segments.json`.

## Procedure (spot-check + reconcile)

### 1) Branch: is the proposed opening duration suspicious?

```python
# candidate: dict with {start,end} seconds; expects start==0 for an opening cut
start = float(candidate.get("start", 0.0))
end = float(candidate.get("end", 0.0))
duration = max(0.0, end - start)

cap = 60.0
if start == 0.0 and duration > cap:
    branch = "SUSPICIOUS"
else:
    branch = "NORMAL"
print(branch, duration)
```

- If `NORMAL`: do a *minimal* boundary check (Step 2 with fewer probes) and proceed.
- If `SUSPICIOUS`: treat the candidate as incorrect until validated; run Step 2 with multiple probes and consider Step 3.

### 2) Extract short probes and check for speech/teaching

Pick multiple timestamps inside the proposed opening plus near the boundary. Extract 3–5s audio clips for quick listening or spectral inspection.

```python
import subprocess

# Times to probe (seconds). Include early/middle/near-boundary.
probe_times = [t for t in (10, 30, 60, 120, end - 5) if t >= 0]
probe_times = sorted(set(int(t) for t in probe_times if t < end))

for t in probe_times:
    out_wav = f"probe_{t:04d}.wav"
    cmd = [
        "ffmpeg", "-y", "-ss", str(t), "-t", "4",
        "-i", audio_path,
        "-ac", "1", "-ar", "16000",
        out_wav,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print({"probes": probe_times})
```

Runtime branch:
- If any probe contains speech/teaching (even quiet): **reject** the candidate opening cut and go to Step 3.
- If all probes are true silence / non-voice setup noise and the boundary probe shows a clear transition into sustained speech: tentatively accept and go to Step 4.

### 3) Re-estimate the boundary with a more robust signal (don’t hardcode)

If the energy-threshold opening looks wrong, re-run a consistent detector with adjusted parameters or a more robust method, then compare candidates.

```python
import json

# candidates: list of dicts like {"name":..., "end":...}
ends = [(c["name"], float(c["end"])) for c in candidates]
ends.sort(key=lambda x: x[1])
spread = ends[-1][1] - ends[0][1] if ends else 0.0

# If spread is large, detectors disagree.
if spread > 10.0:
    action = "DISAGREEMENT_REQUIRES_MORE_PROBES"
else:
    action = "OK_TO_PICK_CONSENSUS"
print({"ends": ends, "spread": spread, "action": action})
```

Runtime branch:
- If detectors disagree (`spread > 10s`): add more probes around each candidate boundary and prefer the earliest boundary that is followed by sustained speech.
- If detectors roughly agree: pick the consensus boundary and proceed.

### 4) Verification before writing removals

Write down the final opening cut boundary and verify it aligns with your probes.

```python
# final_end: chosen boundary in seconds
# probe_labels: dict[int,str] where values include "speech" or "nospeech"

violations = [t for t, lbl in probe_labels.items() if t < final_end and "speech" in lbl]
if violations:
    verdict = "FAIL"
else:
    verdict = "PASS"
print({"verdict": verdict, "violations": violations, "final_end": final_end})
```

Corrective action on failure:
- If `FAIL`: move the opening boundary earlier than the first speech-labeled probe is impossible; therefore **you must reduce** `final_end` to be **at or before** the earliest speech probe (typically set `final_end` just before that probe) and re-probe near the new boundary to confirm.

## Output

Only after `PASS` should you write an opening segment into `remove_segments.json`.
