---
name: syzkaller-build-loop
description: Iterate on syzkaller syscall descriptions by compiling descriptions first, then rebuilding only when needed.
---

# Syzkaller Description Workflow

## Deliverables gate (blocking): persist requested files before building

If the prompt requires writing specific output files, create minimal non-empty stubs at the exact paths and confirm they exist **before** running `make`.

```bash
mkdir -p /path/to/parent
printf '%s\n' '# stub' > /path/to/file.txt
ls -l /path/to/file.txt
sed -n '1,20p' /path/to/file.txt
```

Read references/deliverables-gate.md when the run has produced an empty output inventory, when tool-call persistence is uncertain, or when multiple file paths must be kept in sync. Skip when you are only debugging existing in-tree files and no new deliverables are required.

## Fast loop: validate descriptions before full builds

1. Edit the `.txt` description (and `.const` if you add constants).
2. Run `make descriptions` to compile syzlang and constants.
3. Fix the *first* reported error (types/constants/includes), rerun `make descriptions`, and repeat.
4. Run `make all` only after `make descriptions` is clean.

```bash
cd /path/to/syzkaller
make descriptions
make all
```

Decision rule: if you only changed syzlang text (no generator code), prefer repeated `make descriptions` runs over full rebuilds.

## Inspect existing patterns in-tree

Use grep to find existing idioms (resource types, ioctl variants, struct patterns).

```bash
cd /path/to/syzkaller
grep -R "ioctl\$" sys/linux | head
```

Read references/triage-make-descriptions.md when `make descriptions` errors are unclear or cascade (e.g., unknown type → undefined reference → constant scope issues). Skip when the error message already points to a single missing constant or a single syntax typo.

## Common Pitfalls

- Rebuilding everything repeatedly instead of iterating with `make descriptions` until the first error is fixed.
- Ignoring the *first* error and chasing secondary failures.
- Adding constants but forgetting to create/update the companion `.const` file.
