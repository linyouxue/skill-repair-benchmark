# Extracting and validating syzkaller constants (ioctl-focused)

Use this when you must compute ioctl values, validate `.const` coverage, or debug `make extract`.

## 1) Compute ioctl numbers from `_IO*` macros (branch by kind)

```python
def _IOC(dir_, type_, nr, size):
    # Matches Linux asm-generic/ioctl.h layout (common case)
    _IOC_NRBITS = 8
    _IOC_TYPEBITS = 8
    _IOC_SIZEBITS = 14
    _IOC_DIRBITS = 2

    _IOC_NRSHIFT = 0
    _IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
    _IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
    _IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

    return ((dir_  << _IOC_DIRSHIFT) |
            (size  << _IOC_SIZESHIFT) |
            (type_ << _IOC_TYPESHIFT) |
            (nr    << _IOC_NRSHIFT))

# Runtime branch: choose macro family
kind = "IO"  # one of: IO, IOR, IOW, IOWR

dir_map = {"IO": 0, "IOW": 1, "IOR": 2, "IOWR": 3}
if kind not in dir_map:
    raise ValueError(f"unknown kind: {kind}")

# Generic inputs: type_ is the ioctl type byte, nr is the command number, size is sizeof(arg)
val = _IOC(dir_map[kind], type_=0x00, nr=0x00, size=0)
print(val)
```

Verification:
- If your computed value disagrees with a header definition, stop and inspect the actual kernel headers for: (a) arch-specific `_IOC_*BITS` layout, and (b) the real `sizeof` of the argument type (packing/alignment). Then recompute with corrected parameters before writing the `.const`.

## 2) Decide between manual `.const` vs `make extract`

- **Branch A (no kernel source / headers not accessible):** write a `.const` file manually and list `arches` explicitly.
- **Branch B (kernel source available):** use `make extract TARGETOS=linux SOURCEDIR=... FILES=...` to populate constants.

Verification:
- If `make descriptions` reports `X is defined for none of the arches`, add `X = <value>` to the `.const` file (or ensure extraction produced it) and ensure `arches = ...` includes the intended targets; rerun `make descriptions`.

## 3) Debug `make extract` include failures

```python
import os
from pathlib import Path

syz = Path(os.environ.get("SYZKALLER", "/path/to/syzkaller"))
linux = Path(os.environ.get("LINUX", "/path/to/linux"))

# Runtime branch: quick existence check
if not (syz.exists() and linux.exists()):
    print("Missing syzkaller or linux tree; switch to manual .const workflow")
else:
    print("Found trees; run: make extract TARGETOS=linux SOURCEDIR=... FILES=...")
```

Verification:
- If extraction still cannot find headers, inspect whether the constant lives under `uapi/` vs non-`uapi/`, and confirm the header is reachable from the kernel tree root. If not reachable, revert to manual `.const` with a computed value.
