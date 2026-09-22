---
name: file-organizer
description: Organize files by inventorying the real scope, making reversible plans, executing logged moves/deduplication, and verifying the on-disk end state.
---

# File Organizer

## Classify the task before acting

1. Determine the allowed scope (one folder vs. whole home; include/exclude patterns; delete allowed or archive-only).
2. Decide the primary objective: **restructure**, **deduplicate**, **find** (locate files), or **cleanup** (reduce clutter) — choose one as the first pass.
3. Prefer evidence from the filesystem (actual paths/types/dates) over prompt phrasing; record chosen scope+objective and keep it stable.

## Inspect first (inventory)

- Before creating/downloading any “replacement” files or making mutations, locate the real on-disk dataset directory and record it as the stable **scope root**.
- Inventory the scope root: top-level listing, file counts, and a quick sample of types/names.
- If the goal is “organize everything into a fixed taxonomy”, immediately create the target folders and begin a classify→move loop over *all* files under the scope root.

```bash
set -euo pipefail
root="/path/to/dir"
ls -la "$root" | head
find "$root" -type f | wc -l
find "$root" -maxdepth 2 -type f -printf '%f\n' | head
```

Decision rule: If you cannot point to (and list) the scope root you are about to modify, stop and re-locate it; do not proceed based on prompt wording.

## Plan changes (reversible)

- Propose a target folder taxonomy (by type, purpose, and/or date).
- Specify exact move/rename rules and conflict handling.
- Require confirmation before destructive actions (delete) and prefer “Archive/” when unsure.

```bash
# Dry-run style preview (no changes): print what would be moved
root="/path/to/dir"
dest="$root/Organized"
find "$root" -maxdepth 1 -type f -name '*.pdf' -print | sed "s|^|MOVE -> $dest/PDF/ |" | head
```

Read references/execution-log-and-undo.md when you will perform many moves/renames or any deletion. Skip when only reporting findings.

## Execute moves safely

- Create destination folders first.
- Use copy-then-verify-then-delete (or `mv` with logging) depending on risk tolerance.
- Log every change to a TSV/JSONL file so it can be undone.

```bash
set -euo pipefail
log="organize-log.tsv"
: > "$log"

src="/path/to/dir/a.ext"
dst="/path/to/dir/target/a.ext"
mkdir -p "$(dirname "$dst")"
printf '%s\t%s\n' "$src" "$dst" >> "$log"
mv -n "$src" "$dst"
```

Decision rule: If filename collisions are likely, route into a staging folder and rename systematically before final placement.

## Duplicates (hash-based)

- Use content hashes for exact duplicates; use name/size/date only for candidates.
- Never delete without showing each duplicate set and the keep-rule.

```bash
root="/path/to/dir"
find "$root" -type f -print0 | xargs -0 sha256sum | sort | awk 'NR==1{p=$1} $1==p{print} $1!=p{p=$1; print ""; print}' | head
```

Read references/dedup-workflow.md when you must deduplicate across many folders or choose a canonical copy. Skip when only grouping by file extension.

## Post-write verification

- Re-inventory: counts, total size, and a spot-check that files are where the plan said they would go.
- For fixed-taxonomy tasks ("end with exactly N named folders; no other files left out"), treat completion as a hard gate before termination:
  1) Create the exact required folders under the scope root **before** classification (so every file has a valid destination).
  2) Run at least one full classify→move pass over *all* files in scope (not just top-level).
  3) Run an end-state assertion that detects no-ops/partial passes by checking **leftovers**: no files remain outside the target folders.
  4) **No-op guard:** confirm you actually mutated the filesystem (e.g., move log non-empty / at least one mkdir+move batch executed). If you performed zero mutations, treat the task as incomplete even if you have a plan.
- If any end-state check fails (including the no-op guard), do not stop; continue the classify→move loop (or undo/repair using the move log) until the assertion passes.

```bash
root="/path/to/dir"
# End-state assertion for fixed-taxonomy tasks: no loose files at root level
find "$root" -maxdepth 1 -type f -print
```

Decision rule: Do not end the turn if the command above prints anything; re-run inventory and move the leftovers (or undo the last batch and re-plan collisions).

Read references/fixed-taxonomy-completion-gate.md when the deliverable is “exactly N named folders and nothing left outside them” or when a prior attempt produced a no-op/partial organization. Skip when you are only reorganizing a subset or leaving files in place is allowed.

## Common pitfalls

- Acting on assumptions from the prompt instead of inspecting and freezing the real scope root on disk.
- Starting downloads/content generation as a substitute for the provided dataset instead of organizing the existing files.
- Ending early on fixed-taxonomy tasks without an explicit end-state assertion (folders exist + zero leftover files outside them), including stopping after doing **no mutations**.
- Making irreversible changes (delete/overwrite) without a plan, confirmation, and an undo log.
- Flattening project directories and breaking relative paths/configs.
- Treating “same name” or “same size” as duplicates without hashing.
