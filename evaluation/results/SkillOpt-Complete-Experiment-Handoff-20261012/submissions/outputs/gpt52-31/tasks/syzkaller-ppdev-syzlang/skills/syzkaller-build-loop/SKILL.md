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


#    The base filename must match exactly (example: dev_ppdev.txt + dev_ppdev.txt.const)
#    Place both files directly under sys/linux/
# 3. Compile descriptions
make descriptions

# 4. Build syzkaller
make all
```

## Quick Rebuild (After Minor Edits)

If you only changed descriptions (not constants):

```bash
cd /opt/syzkaller
make descriptions   # Runs syz-sysgen to compile descriptions
```

If you add new constants, update the `.const` file first.


For new device descriptions, develop incrementally:

```bash
# Start with only:
# - resource definition
# - syz_open_dev opener
# - minimal structs/constants
make descriptions

# Then add ioctls one-by-one, running:
make descriptions
# after each addition
```

This isolates which ioctl, struct, or constant introduced a failure.
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
- The constant is missing from the `.const` file, or the file does not declare supported arches
- Ensure the file contains the correct header, for example:
```text
arches = amd64, 386
```
- Verify the `.const` filename exactly matches the `.txt` filename
- Add the constant with the correct value to `sys/linux/your_file.txt.const`

### Missing reference
```
undefined reference to 'some_type'
```
- Type defined in another file not being found
- Check includes or existing type definitions


### Parse/type errors from ioctl arguments
```
wrong type
cannot parse
unknown field
```
- Structs must be defined before first use
- Check pointer directions (`ptr[in]`, `ptr[out]`, `ptr[inout]`) against the ioctl semantics
- Verify ioctl argument types match the kernel header definitions

### Finding the exact failing definition
`make descriptions` error output usually includes the generated file and line number from `syz-sysgen`.

Use the referenced filename/line to identify the exact ioctl or struct causing the failure:

```bash
make descriptions 2>&1 | tee /tmp/syz.log
grep -n "error\|undefined\|cannot parse" /tmp/syz.log
```

Most failures come from:
- a missing constant
- a struct defined after use
- a mismatched pointer direction/type
- a `.const` file scoped to no arches
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
