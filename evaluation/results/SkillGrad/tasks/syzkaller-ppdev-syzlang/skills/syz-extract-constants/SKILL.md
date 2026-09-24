---
name: syz-extract-constants
description: Define and validate kernel constants (ioctls, flags) for syzkaller syzlang descriptions.
---

# Defining Constants in Syzlang

## Deliverables gate (blocking): write required files immediately, then iterate

If the task requests new/updated files at specific paths, treat “files exist and are non-empty on disk” as a hard precondition to any extraction/build work.

```bash
mkdir -p /path/to/parent
printf '%s\n' '# stub' > /path/to/file.txt
ls -l /path/to/file.txt
sed -n '1,20p' /path/to/file.txt
```

Read references/deliverables-gate.md when the run has zero/uncertain tool-call persistence or when failures show an empty output inventory. Skip when the caller guarantees the files are already created at the exact required paths.

## Plan: choose a constant source, then verify in the build

1. Decide whether you can extract from kernel headers or must define constants manually.
2. Keep constants architecture-scoped: declare `arches = ...` for the values you provide.
3. After any constant change, run `make descriptions` and fix the first reported missing/undefined constant before proceeding.

## Provide constants via a companion `.const` file

Create a `.const` file next to the `.txt` description file. Use it when you cannot (or do not want to) depend on a kernel source tree.

```text
# Constants for a syzlang file
arches = arch1, arch2
CONST_A = 0
CONST_B = 1
```

Decision rule: prefer a `.const` file when the environment lacks kernel headers or the constants are stable across architectures.

## Extract constants from kernel headers (`make extract`)

Use the build target rather than calling `syz-extract` directly; it wires include paths and selects the right extractor.

```bash
cd /path/to/syzkaller
make extract TARGETOS=linux SOURCEDIR=/path/to/linux FILES=sys/linux/your_file.txt
```

Read references/extract-constants.md when you need to compute or sanity-check ioctl numbers (e.g., `_IO*` macros) or when extraction fails due to include-path issues. Skip when you are only adding non-ioctl integer constants with known values.

## Common Pitfalls

- Defining a constant but forgetting to list compatible `arches`, so it becomes “defined for none of the arches”.
- Using task/environment assumptions (“kernel source exists here”) instead of checking whether headers are actually present.
- Calling `bin/syz-extract` directly and missing the build-system include configuration.
