---
name: syzkaller-build-loop
description: Build and validate syzkaller after editing syzlang descriptions while ensuring final artifacts are correct in the graded target path.
---

# Build Loop for Description Changes

## Minimal loop

```bash
cd /opt/syzkaller
make descriptions
make all
```

## Constrained environments: verify the graded target path

1. Before editing, confirm whether the *graded* tree/path is writable and whether the file already exists; choose edit-in-place vs working in a writable copy.
2. If you work in a writable copy, explicitly copy the final `.txt` and `.const` back into the graded target tree.
3. After **every** write/copy-back, immediately re-open the exact target files and sanity-check syntax and required blocks (includes/resources/types/ioctl lines).
4. Run `make descriptions` in the tree that contains the graded target files.

Decision rule: If you cannot re-read and build using the tree that contains the graded target paths, treat the task as incomplete and report the specific blocker (permission/tool restriction/path mismatch).

## When constants change

- Update the companion `.const` file first.
- Then run `make descriptions` to compile descriptions+constants.

Decision rule: If the task was “add new ioctls from a header”, run a coverage reconciliation (header macros ↔ `.txt` const names) before the build to avoid compiling an incomplete interface.

## Common errors (and where to look)

- `unknown type ...`: type missing or declared after use → define earlier or reuse an existing type.
- `... is defined for none of the arches`: missing `.const` entry or arches mismatch → add/adjust `.const`.
- `undefined reference ...`: missing include/definition → search for canonical type in `sys/linux/` and reuse.

```bash
grep -R "ioctl\$" -n sys/linux | head
```
