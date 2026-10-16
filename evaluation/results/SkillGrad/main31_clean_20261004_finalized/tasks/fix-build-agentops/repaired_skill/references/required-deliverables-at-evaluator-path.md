# Required deliverables at evaluator path (patch/log/report)

Read this when the task requires writing an artifact (often a patch diff) to a **specific absolute path** and the harness reports a missing deliverable even though tests/build may be green. Skip when success is determined only by test results.

## Goal

Create the artifact exactly where the evaluator expects it, then verify presence and basic correctness using shell primitives that are robust in minimal environments.

## Procedure (branched)

### Branch A — The deliverable is a git patch/diff file

1. Locate the required absolute output path(s) from the prompt/evaluator message.
2. Generate the diff from your working tree changes.
3. Write it to the required path.
4. Verify the file exists, is non-empty, and looks like a unified diff.

```python
import os
import subprocess
from pathlib import Path

out_path = Path(os.environ.get("OUT_PATH", "/abs/path/to/patch_1.diff"))
out_path.parent.mkdir(parents=True, exist_ok=True)

def sh(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)

# Create the patch from real edits
patch = sh(["git", "--no-pager", "diff"])
out_path.write_text(patch, encoding="utf-8")

# Minimal verification (avoid fancy ls flags/aliases)
assert out_path.exists(), "deliverable missing: file not created"
assert out_path.stat().st_size > 0, "deliverable empty: diff had no content"

head = "".join(out_path.read_text(encoding="utf-8", errors="replace").splitlines(True)[:20])
assert "diff --git" in head or head.startswith("---"), "deliverable not a unified diff"
print({"ok": True, "bytes": out_path.stat().st_size})
```

Runtime branch: if `git diff` is empty but you expected changes
- Confirm you edited the correct working tree and files are not ignored.
- Check status (`git status --porcelain`) and regenerate the diff.

### Branch B — The deliverable is a log/report/text file

1. Write the file to the required absolute path.
2. Verify the file exists, is non-empty, and contains an expected marker (header, summary line, etc.).

```python
import os
from pathlib import Path

out_path = Path(os.environ.get("OUT_PATH", "/abs/path/to/report.txt"))
out_path.parent.mkdir(parents=True, exist_ok=True)

out_path.write_text("<report header>\n<content>\n", encoding="utf-8")

assert out_path.exists(), "deliverable missing"
assert out_path.stat().st_size > 0, "deliverable empty"
text = out_path.read_text(encoding="utf-8", errors="replace")
assert "<report header>" in text, "deliverable lacks expected marker"
print({"ok": True, "lines": len(text.splitlines())})
```

## Shell verification snippets (safe primitives)

Use these when you want to verify from a shell without relying on locale-specific flags:

- `test -s "/abs/path" && echo OK || echo MISSING_OR_EMPTY`
- `wc -l "/abs/path"`
- `head -n 20 "/abs/path"`

Runtime branch: if any verification command errors
- Immediately retry using **simpler** commands (avoid `ls --color`, `exa`, or copied unicode dashes).
- If it still errors, verify via Python (`Path.exists()`, `stat().st_size`, `read_text(errors="replace")`).

## Verification + corrective action

1. **Verify:** artifact exists at the exact required absolute path and `stat().st_size > 0`.
   - If not: recreate parent directories, rewrite the file, and re-check with `test -s` / Python `Path`.
2. **Verify:** artifact content matches the expected format (diff header or report marker).
   - If not: regenerate from the source of truth (`git diff` for patches; the tool that produced the report for reports), then rewrite and re-check.
3. Only finish once verification passes; treat “tests green” as necessary but not sufficient when an explicit deliverable is required.
