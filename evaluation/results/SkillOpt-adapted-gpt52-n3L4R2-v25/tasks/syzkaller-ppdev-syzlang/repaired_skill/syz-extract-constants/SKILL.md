---
name: syz-extract-constants
description: Defining and extracting kernel constants for syzkaller syzlang descriptions
---

# Defining Constants in Syzlang

## Overview

Syzkaller needs to know the actual values of kernel constants (ioctl numbers, flags, etc.) to generate valid fuzzing programs. There are two ways to provide these values:

1. **Manual `.const` file** - Define constants directly in a companion file
2. **`syz-extract` tool** - Extract values from kernel source headers (requires kernel source)

## Method 1: Manual Constants File (Recommended when no kernel source)

Create a `.const` file alongside your `.txt` file with the constant values:

### File naming
- Syzlang description: `sys/linux/dev_ppdev.txt`
- Constants file: `sys/linux/dev_ppdev.txt.const`

### Constants file format

```
# Constants for your syzlang descriptions
arches = amd64, 386
PPCLAIM = 28811
PPRELEASE = 28812
IEEE1284_MODE_NIBBLE = 0
IEEE1284_MODE_BYTE = 1
```

The `arches` line declares which architectures these constants are valid for. For architecture-independent constants (like ioctls), list all architectures.

### Calculating ioctl values

Do not derive ppdev ioctl constants from only the command letter and ordinal. Read each declaration in the target `linux/ppdev.h` and identify `_IO`, `_IOR`, `_IOW`, or `_IOWR`, then use the declaration's actual payload type. The encoded size is the target compiler's `sizeof` value, so structure-based commands can differ between amd64 and 386. Prefer values emitted by `syz-extract` or by a C probe that includes the target headers; record the resulting integer exactly in the `.const` file rather than guessing or applying a hard-coded payload size.

## Method 2: Using syz-extract (Requires kernel source)

If kernel source is available:

```bash
cd /opt/syzkaller

# Extract constants for a specific file
make extract TARGETOS=linux SOURCEDIR=/path/to/linux FILES=sys/linux/dev_ppdev.txt
```

Use the target kernel tree whenever possible: `make extract TARGETOS=linux SOURCEDIR=/path/to/linux FILES=sys/linux/dev_ppdev.txt` resolves the included UAPI headers and emits architecture-specific values. If extraction cannot be run, compile a small probe including `linux/ppdev.h` and `linux/parport.h` and print every referenced macro, once with amd64 headers and once with 386 headers. In either case, verify the generated values against the exact headers used by the description.

## After Defining Constants

After creating the `.const` file, build syzkaller:

```bash
cd /opt/syzkaller
make descriptions  # Compiles descriptions + constants
make all           # Full build
```

## Common Errors

### "is defined for none of the arches"
This means the constant is used in the `.txt` file but not defined in the `.const` file.
- Add the missing constant to your `.const` file
- Ensure `arches` line lists the target architectures
PPCLAIM is defined for none of the arches
```

Solution: Run `make extract` with the correct kernel source path and FILES parameter.

### Missing headers
```
cannot find include file: uapi/linux/ppdev.h
```

Solution: Check the kernel source path and ensure headers are properly configured.

### "unknown file"
```
unknown file: sys/linux/dev_ppdev.txt
```

Solution: Use `make extract FILES=...` instead of calling `bin/syz-extract` directly.

## Example Workflow

1. Write the syzlang description file (`sys/linux/dev_ppdev.txt`)
2. Run `make extract TARGETOS=linux SOURCEDIR=/opt/linux/source FILES=sys/linux/dev_ppdev.txt`
3. Run `make generate` to regenerate Go code
4. Run `make` to build syzkaller
5. Test with `make descriptions` to verify everything compiles


## ppdev-specific extraction checklist

For `sys/linux/dev_ppdev.txt`, build the constants file from the description's symbol inventory, not from a partial example:

1. Read the target `linux/ppdev.h` and `linux/parport.h` (normally under `include/uapi`) and enumerate every symbol referenced by the description. This must include all 23 ppdev ioctl commands and every referenced IEEE1284 mode, phase, ppdev, and parport flag constant. Preserve the exact spelling used in the `.txt` file.
2. For each ioctl, copy its declaration's direction and payload type from `ppdev.h`. Extract the value with the target headers for both amd64 and 386, because `_IOR`/`_IOW`/`_IOWR` values incorporate the compiler-dependent size of the pointed-to type or structure. Do not substitute guessed arithmetic or values from another architecture.
3. Ensure `sys/linux/dev_ppdev.txt.const` begins with exactly `arches = amd64, 386` and contains every symbol referenced by the description, with no missing aliases or unverified extras. Compare the symbol set in the `.txt` against the entries in `.txt.const`, then compare every recorded value with header extraction or the two-architecture C probe.
4. Finish with `make descriptions` and the requested amd64 build. A successful parse is insufficient if any of the 23 commands, their in/out direction, structure-size-dependent value, mode/phase constant, or flag constant was omitted or mismatched.
