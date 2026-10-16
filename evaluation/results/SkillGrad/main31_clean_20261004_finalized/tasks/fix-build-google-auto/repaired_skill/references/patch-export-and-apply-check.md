# Patch export + applicability check (git-style)

Use this procedure when the task expects a `patch_1.diff` output (or similar) and your fix is already applied in the working tree.

## Goal

Produce a structurally valid patch that applies cleanly, without hand-editing hunk headers or context.

## Procedure

### 1) Start from a clean baseline (branch)

If you previously tried to apply a patch or edited files in-place, reset first so you know what the patch contains.

```bash
git status --porcelain

# Branch A: you have unwanted local changes → discard them
if [ -n "$(git status --porcelain)" ]; then
  git reset --hard
fi

# Branch B: repo is clean → proceed
```

### 2) Apply the fix by editing real files

Edit the files directly (editor, `sed`, etc.). Do not create a patch file yet.

```bash
# Example: open and edit files, then confirm only intended files changed
git status --porcelain
git diff
```

### 3) Export the patch from the working tree

```bash
git diff > patch_1.diff
```

### 4) Validate that the patch is applicable

Prefer to check in a clean state, so you're testing real applicability rather than “already-applied”.

```bash
# Branch A: check by applying to a clean tree (recommended)
git reset --hard
if git apply --check patch_1.diff; then
  git apply patch_1.diff
else
  echo "patch does not apply; regenerate from working tree edits" >&2
  exit 1
fi

# Branch B: if you cannot reset, at least run a structural check
# git apply --check patch_1.diff
```

### 5) Verification step

Run the target command after applying the patch.

```bash
# Replace with the task's exact command
mvn -B -e verify
```

**If verification fails:**
1) keep the patch workflow the same (edit files → `git diff` → `git apply --check`),
2) fix the *new* first failure, and
3) re-export a fresh patch (do not hand-edit `patch_1.diff` hunks).
