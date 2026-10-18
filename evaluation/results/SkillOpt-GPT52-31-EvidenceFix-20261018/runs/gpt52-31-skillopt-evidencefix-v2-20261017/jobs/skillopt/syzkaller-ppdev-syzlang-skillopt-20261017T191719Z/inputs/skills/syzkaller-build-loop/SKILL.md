---
name: syzkaller-build-loop
description: Full build workflow for adding new syscall descriptions to syzkaller
---

# Syzkaller Description Workflow

## Full Build Loop for New Descriptions

When adding new syscall descriptions, follow this workflow:

```bash
cd /opt/syzkaller

# 1. Write/edit your .txt file in sys/linux/

# 2. Create a .const file with constant values (see syz-extract-constants skill)
#    The .const file should be named: sys/linux/your_file.txt.const

# 3. Compile descriptions
make descriptions



# 3a. Pre-verifier semantic validation (do this BEFORE relying on make/tests)
# `make descriptions` can succeed even when ioctl signatures/const identifiers are wrong.
# Validate ioctl$ definitions match the underlying _IO* macro form:
#   - _IO(...)      => ioctl$NAME(fd fd_*, cmd const[NAME])   # exactly 2 args
#   - _IOR(...)     => ioctl$NAME(fd fd_*, cmd const[NAME], arg ptr[out, T])
#   - _IOW(...)     => ioctl$NAME(fd fd_*, cmd const[NAME], arg ptr[in,  T])
#   - _IOWR(...)    => ioctl$NAME(fd fd_*, cmd const[NAME], arg ptr[inout, T])
# Quick audit helpers:
#   grep -n '^ioctl\$' sys/linux/your_file.txt
#   # Look specifically for accidental dummy args on _IO commands:
#   grep -n 'ioctl\$.*const\[[^]]\+\].*arg' sys/linux/your_file.txt



# 3b. Validate constant coverage before testing/building
# Gate on identifier completeness: every const[...] reference MUST exist in the
# matching .const file with exact identifier spelling (case/prefix/suffix).
# This includes ioctl command names (e.g., PPCLAIM) and verifier-facing flags.
# Example workflow:
#   refs=$(grep -o 'const\[[^]]*\]' sys/linux/your_file.txt | sed 's/const\[\([^]]*\)\]/\1/' | sort -u)
#   defs=$(grep -E '^[A-Z][A-Z0-9_]*\s*=' sys/linux/your_file.txt.const | cut -d'=' -f1 | tr -d ' ' | sort -u)
#   diff -u <(printf "%s\n" "$refs") <(printf "%s\n" "$defs")
# 4. Final gate: compile descriptions AND full build
make all
# Passing `make descriptions` alone is not sufficient; run the verifier/tests after this when available.

```

## Quick Rebuild (After Minor Edits)

If you only changed descriptions (not constants):



Note: even for “minor edits”, re-check ioctl$ signature semantics when touching ioctls.
A common regression is adding a dummy third argument to _IO ioctls; verifier expects 2-arg form.

```bash
cd /opt/syzkaller
make descriptions   # Runs syz-sysgen to compile descriptions
```

If you add new constants, update the `.const` file first.


Re-run BOTH checks after edits: (1) ioctl$ signature semantics (_IO vs _IOR/_IOW/_IOWR with correct ptr[in/out] direction) and (2) constant coverage (every const[...] identifier present in .txt.const). Exact spelling mismatches or wrong ioctl arity can pass `make descriptions` yet fail in verifier/tests.
## Common Errors

### Unknown type
```
unknown type foo_bar
```
- Type not defined, or defined after first use
- Define all types before using them

### Constant not available / defined for none of the arches
```
SOME_CONST is defined for none of the arches
```
- The constant isn't in the `.const` file
- Add it to `sys/linux/your_file.txt.const` with the correct value


- Also verify the identifier spelling exactly matches the `.txt` references
- Constants referenced only in ioctl definitions or verifier checks may not fail until runtime tests
- Compare referenced constants against `.const` entries with `grep`/`diff` before running full builds
### Missing reference
```
undefined reference to 'some_type'
```
- Type defined in another file not being found
- Check includes or existing type definitions

## Exploring Existing Code

Find examples of patterns:
```bash
grep -r "pattern" /opt/syzkaller/sys/linux/
```

Useful searches:
- `resource fd_` - How other fd resources are defined
- `ioctl\$` - Ioctl definition patterns
- `read\$` / `write\$` - Read/write specializations
- `struct.*{` - Struct definition patterns

## Files to Reference

- `sys/linux/socket.txt` - Network types (ifreq_t, sockaddr, etc.)
- `sys/linux/sys.txt` - Basic syscall patterns
- `sys/linux/fs.txt` - File operations
