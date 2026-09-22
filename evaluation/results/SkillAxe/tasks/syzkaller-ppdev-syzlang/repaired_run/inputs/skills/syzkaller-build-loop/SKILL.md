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

## Post-build sanity checks (catches missing constants)

`make descriptions` validates syntax and most constant references, but it’s still easy to accidentally omit a required constant line (or write it in a way that doesn’t get parsed as expected). Add a quick audit step whenever you introduce a new `.const` file:

1) Ensure every `const[...]` referenced in the `.txt` has a `NAME = ...` line in the `.const`:

```bash
FILE=sys/linux/your_file.txt
CONST=${FILE}.const
for c in $(grep -oE 'const\[[A-Z0-9_]+\]' $FILE | sed 's/const\[//;s/\]//' | sort -u); do
  grep -qE "^${c}\\s*=" $CONST || echo "MISSING CONST: ${c}"
done
```

2) If you’re defining ioctls by hand, cross-check at least one or two “anchor” values from the header encoding (e.g., simple `_IO()` ioctls like `...CLAIM`, `...RELEASE`) to confirm parsing and arithmetic are correct.

These checks are generic and avoid task-instance hacks; they prevent silent omissions that only show up in downstream validation.

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
