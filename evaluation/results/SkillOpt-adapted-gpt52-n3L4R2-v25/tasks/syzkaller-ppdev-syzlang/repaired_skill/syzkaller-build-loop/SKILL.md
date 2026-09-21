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



## ppdev Completion Checklist and Validation Loop

For Linux parallel-port support, validate the complete ppdev interface rather than relying on a generic successful description build:

1. Confirm the exact files exist and are paired:
   ```bash
   test -f /opt/syzkaller/sys/linux/dev_ppdev.txt
   test -f /opt/syzkaller/sys/linux/dev_ppdev.txt.const
   ```
   The companion constants file must match `dev_ppdev.txt` exactly with the `.const` suffix.
2. Compare `dev_ppdev.txt` with `linux/ppdev.h` and `linux/parport.h`. Check for `include <linux/ppdev.h>`, `include <linux/parport.h>`, `resource fd_ppdev[fd]`, a `syz_open_dev` opener for `/dev/parport#` returning `fd_ppdev`, `ppdev_frob_struct { mask, val }`, the IEEE1284 mode flags, and the ppdev/parport flag sets.
3. Enumerate the header's 23 unique ppdev ioctl variants and ensure each has exactly one syzlang definition. Derive each argument's scalar, pointer, structure, and in/out direction from the header's `_IO`, `_IOR`, `_IOW`, or `_IOWR` declaration; verify structure sizes and do not substitute a merely similar ioctl.
4. Audit `dev_ppdev.txt.const` as a complete inventory of every referenced ioctl and flag symbol. Require `arches = amd64, 386`, and verify every referenced constant is defined for both architectures. Resolve unknown types or constants, unavailable architecture definitions, duplicate syscall names, malformed or unresolved includes, extraction problems, and ioctl size or direction mismatches instead of masking them by changing the architecture list.
5. Run the requested checks and inspect all diagnostics:
   ```bash
   cd /opt/syzkaller
   make descriptions
   make all TARGETOS=linux TARGETARCH=amd64
   ```
6. After generation, perform a final header-to-description audit: recount the 23 ioctl variants, check that none is missing or duplicated, and recheck every referenced constant, flag, structure, opener, and argument direction against the two kernel headers.
