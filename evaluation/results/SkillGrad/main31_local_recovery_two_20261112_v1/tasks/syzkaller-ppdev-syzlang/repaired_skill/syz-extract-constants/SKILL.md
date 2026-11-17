---
name: syz-extract-constants
description: Define and extract kernel constants (ioctl numbers, flags) for syzkaller syzlang descriptions.
---

# Constants for Syzlang Descriptions

## Choose an extraction strategy

1. Prefer `make extract ... FILES=...` when you have kernel source available.
2. Otherwise, provide a manual `.const` file, but keep the symbol set aligned with what the `.txt` references.

```bash
cd /opt/syzkaller
make extract TARGETOS=linux SOURCEDIR=/path/to/linux FILES=sys/linux/your_file.txt
```

Decision rule: If the task is graded by strict diff, treat “symbol set alignment” (same names, no omissions) as more important than how you computed values.

## Manual `.const` files (minimal rules)

- Place constants in `sys/linux/<file>.txt.const` next to the `.txt`.
- Ensure **every** `const[NAME]` and `flags[SET, NAME]` token in the `.txt` has a matching `NAME = <value>` line in the `.const`.

```txt
arches = amd64, 386
SOME_IOCTL = 0
SOME_FLAG = 1
```

Read references/ioctl-coverage-reconcile.md when you are creating new ioctl descriptions from a header and need to ensure the `.const` symbol set matches the header-derived macro list. Skip when you are only adjusting numeric values for existing constants.

# Common Errors (build-time)

- `X is defined for none of the arches`: constant referenced in `.txt` missing or `arches` mismatch → add it to `.const` and include the needed arches.
- `unknown file: ...`: use `make extract ... FILES=...` (not a raw `syz-extract` call).
