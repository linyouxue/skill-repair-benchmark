# Deliverables gate: prevent empty output inventory (syzkaller tasks)

Use this when the task requires creating/writing specific output files and runs have previously ended with **no persisted artifacts**.

## Procedure (with a hard early guardrail)

1. List every required deliverable as an **absolute path**.
2. For each path, create parent dirs and write a **minimal non-empty stub** (so the run is gradeable even if later steps fail).
3. **Checkpoint (must pass before deeper work):** `ls -l` all paths and preview each with `sed -n '1,40p'`.
4. Only then do build/extract/triage steps.

```python
from pathlib import Path

paths = [Path("/abs/path/to/file_a"), Path("/abs/path/to/file_b")]

for p in paths:
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists() or p.stat().st_size == 0:
        p.write_text("# stub\n", encoding="utf-8")

# Runtime branch: verify and prescribe corrective action
missing = [p for p in paths if (not p.exists() or p.stat().st_size == 0)]
if missing:
    raise SystemExit(f"Deliverables gate failed; create/write these first: {missing}")
else:
    print("Deliverables gate passed")
```

## Verification and corrective action

Verification:
- Run `ls -l <paths...>` and ensure each file exists and is non-empty.
- Run `sed -n '1,40p' <path>` for each deliverable to confirm you are writing the intended file (not a lookalike path).

If verification fails:
- **Do not** continue with build/debugging.
- Re-run the stub creation for the failing paths, then repeat the checkpoint until it passes.

## Post-build re-check (persistence)

Runtime branch:
- If you ran any `make ...` that could regenerate or move files, re-run the same `ls/sed` checkpoint.
- If the files changed unexpectedly, re-apply your edits to the correct on-disk paths, then rerun `make descriptions` and checkpoint again.
