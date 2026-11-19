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
- Syzlang description: `sys/linux/your_file.txt`
- Constants file: `sys/linux/your_file.txt.const`

### Constants file format

```
# Constants for your syzlang descriptions
arches = 386, amd64, arm, arm64, mips64le, ppc64le, riscv64, s390x
SOME_IOCTL = 0x1234
SOME_FLAG = 1
```

The `arches` line declares which architectures these constants are valid for.

You can also provide per-arch overrides inline:

```
SOME_CONST = 100, amd64:200
```

This is useful when the value depends on ABI details (e.g., `sizeof(struct ...)` used in ioctl encoding differs between 32-bit and 64-bit).

### Calculating ioctl values

Linux ioctl numbers are encoded as:
- `_IO(type, nr)` = `(type << 8) | nr`
- `_IOR(type, nr, size)` = `(2 << 30) | (size << 16) | (type << 8) | nr`
- `_IOW(type, nr, size)` = `(1 << 30) | (size << 16) | (type << 8) | nr`
- `_IOWR(type, nr, size)` = `(3 << 30) | (size << 16) | (type << 8) | nr`

Example (an `_IO` ioctl that does not encode a size):
- `_IO('X', 0x01)` = `(0x58 << 8) | 0x01` = `0x5801`

Caveat: `_IOR/_IOW/_IOWR` ioctls *encode the size of the referenced type*. If that type includes `long`/pointers or other ABI-dependent fields, the ioctl number can differ between 32-bit and 64-bit.

## Method 2: Using syz-extract (Requires kernel source)

If kernel source is available:

```bash
cd /opt/syzkaller

# Extract constants for a specific file
make extract TARGETOS=linux SOURCEDIR=/path/to/linux FILES=sys/linux/your_file.txt
```

**Note:** Some environments may not include kernel sources. In that case, use Method 1 (manual `.const` file) instead.

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
SOME_CONST is defined for none of the arches
```

Solution: Add the missing constant to the `.const` file, or (if you have kernel sources) run `make extract` with the correct `SOURCEDIR` and `FILES=`.

### Missing headers
```
cannot find include file: uapi/linux/some_header.h
```

Solution: Ensure your `include <...>` paths match syzkaller's known include roots (often `include <uapi/...>` or `include <linux/...>`), and that the headers exist in the target environment.

### "unknown file"
```
unknown file: sys/linux/your_file.txt
```

Solution: Ensure the file path is correct and that you're running extraction from the syzkaller tree. Prefer `make extract FILES=...` over calling `bin/syz-extract` directly.

## Example Workflow

1. Write the syzlang description file (`sys/linux/your_file.txt`)
2. Run `make extract TARGETOS=linux SOURCEDIR=/path/to/linux FILES=sys/linux/your_file.txt`
3. Run `make generate` to regenerate Go code
4. Run `make` to build syzkaller
5. Test with `make descriptions` to verify everything compiles
