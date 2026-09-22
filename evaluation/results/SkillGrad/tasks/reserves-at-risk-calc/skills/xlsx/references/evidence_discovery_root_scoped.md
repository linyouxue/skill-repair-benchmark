# Evidence discovery is root-scoped (diagnosis)

Use this when you cannot access verifier evidence (missing file, or an error like “escapes the allowed project root”). The goal is to locate *any* in-root artifacts that explain what check failed, without guessing absolute paths.

## Procedure (with branches)

```python
from __future__ import annotations

import json
from pathlib import Path

def list_existing(root: Path, rel_globs: list[str]) -> list[Path]:
    out: list[Path] = []
    for g in rel_globs:
        out.extend((root / g.split("/")[0]).glob("/".join(g.split("/")[1:])) if "/" in g else root.glob(g))
    # de-dup, stable
    seen = set()
    uniq = []
    for p in sorted(out):
        if p not in seen and p.exists():
            seen.add(p)
            uniq.append(p)
    return uniq

root = Path(root_dir_str)

# Branch A: root itself not accessible -> stop; you cannot diagnose safely
if not root.exists():
    raise FileNotFoundError(
        f"Project root not found/readable: {root}. "
        "Use an in-sandbox path (e.g., the batch/iter directory) as root_dir."
    )

# Prefer explicit candidates first, then fall back to globs.
explicit = [
    "verifier/evidence.json",
    "verifier/results.json",
    "verifier/report.json",
    "verifier/report.txt",
    "assessment.json",
    "trace.jsonl",
]

p = next((root / rel for rel in explicit if (root / rel).exists()), None)

# Branch B: explicit paths missing -> enumerate plausible in-root artifacts
if p is None:
    candidates = list_existing(
        root,
        rel_globs=[
            "verifier/*.json",
            "verifier/*.txt",
            "*.json",
            "*.jsonl",
        ],
    )
    if not candidates:
        raise RuntimeError(
            "No in-root verifier/assessment/trace artifacts found. "
            "Classify this as a harness/evidence-collection constraint and avoid domain-skill patches."
        )
    p = candidates[0]

# Load a small preview for human/agent triage
suffix = p.suffix.lower()
if suffix == ".json":
    preview = json.loads(p.read_text())
elif suffix == ".jsonl":
    preview = p.read_text().splitlines()[:50]
else:
    preview = p.read_text().splitlines()[:200]

print({"picked": str(p), "preview_type": suffix, "preview": preview})
```

## Verification and corrective action
- If you cannot find *any* in-root artifacts: stop and label as harness/evidence-collection issue; do not speculate about spreadsheet mistakes.
- If you find artifacts but they don’t identify the first failing check: broaden the in-root glob list (still rooted) and re-run; only after evidence is found should you propose changes to the spreadsheet procedure.
