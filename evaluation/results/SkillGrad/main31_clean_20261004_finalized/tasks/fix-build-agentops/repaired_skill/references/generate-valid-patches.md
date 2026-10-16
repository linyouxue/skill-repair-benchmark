# Generate valid patches (avoid handcrafted corrupt diffs)

Use this when patch application fails with errors like **"corrupt patch"**, **"hunk FAILED"**, or repeated header/line-count mismatches.

## Goal

Produce a patch from real file edits so the diff format is correct by construction, then verify the patch applies cleanly and reproduces the intended change.

## Procedure (branched)

1. **Return to a clean baseline** (so your patch represents only your intended change).
2. **Edit files normally**, then let `git diff` generate the unified diff.
3. **Verify apply** on a clean tree.

### Branch A — You have a git repo and can commit/reset

```python
import subprocess
from pathlib import Path

def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()

# 1) Clean baseline
run(["git", "reset", "--hard"])
run(["git", "clean", "-fd"])

# 2) Make edits in working tree (manual editor step)

# 3) Produce patch from real edits
patch_text = run(["git", "diff"])
Path("change.patch").write_text(patch_text)

# 4) Verify patch applies to clean tree
run(["git", "reset", "--hard"])
run(["git", "apply", "--check", "change.patch"])
run(["git", "apply", "change.patch"])
```

### Branch B — No git history available (or you must avoid reset)

```python
import shutil
import subprocess
from pathlib import Path

repo = Path(".").resolve()
backup = Path(".backup_worktree")

# 1) Snapshot
if backup.exists():
    shutil.rmtree(backup)
shutil.copytree(repo, backup, dirs_exist_ok=True)

# 2) Make edits in working tree (manual editor step)

# 3) Generate a patch by diffing snapshot vs current
patch = subprocess.check_output(
    ["diff", "-u", "-r", str(backup), str(repo)],
    text=True,
)
Path("change.patch").write_text(patch)

# 4) Verification is different here: restore backup and ensure you can re-apply
shutil.rmtree(repo / "<edit carefully: restore step depends on environment>", ignore_errors=True)
```

## Verification + corrective action

- **Verify:** `git apply --check change.patch` (or equivalent) succeeds.
  - If it fails, **do not** hand-edit hunk headers. Instead:
    1) return to a clean baseline,
    2) re-make the edits,
    3) re-generate the patch from `git diff`.

- **Verify:** After applying the patch, re-run the evaluator boundary (install + tests).
  - If tests are still red, keep the patch method but change *content*: follow the first failing assertion/error and iterate.

## Notes

- Prefer `git diff` over composing unified diffs manually; most “corrupt patch” issues come from malformed hunk ranges, stray context lines, or missing trailing newlines.
- Keep one patch = one coherent change set; regenerate rather than “patching the patch.”
