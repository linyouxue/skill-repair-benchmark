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

## Preflight: make sure the tree is writable

`make descriptions` and `make all` write generated files and build artifacts under the syzkaller tree (e.g., `./bin/`, `sys/*/gen/`, and sometimes other generated headers). In some environments you can edit `sys/linux/` but cannot write to the repo root, which will make builds fail.

Before you iterate, sanity-check writability:

```bash
cd /opt/syzkaller

# Can we create build outputs here?
test -w . && echo "repo writable" || echo "repo NOT writable"
```

If the repo root is not writable, create a writable working copy (or clone) and run builds there:

```bash
SYZ_SRC=/opt/syzkaller
SYZ_WORK=$HOME/syzkaller-work

cp -R "$SYZ_SRC" "$SYZ_WORK"
# Apply your sys/linux/*.txt + *.const edits in $SYZ_WORK too (edit there or copy the files).

cd "$SYZ_WORK"
make descriptions
make all TARGETOS=linux TARGETARCH=amd64
```

If the task requires the final files to live under `/opt/syzkaller/sys/linux/`, copy just the finished `.txt`/`.const` back after validation.

## Troubleshooting common build blockers

### "fatal: detected dubious ownership in repository"
Syzkaller's Makefile calls git to embed a revision string. If your user does not own the repo directory, git may refuse to run.

Fix (safe for a one-user container):

```bash
git config --global --add safe.directory "$(pwd -P)"
```

Then re-run `make descriptions`.

### "permission denied" when creating `./bin/` or other outputs
This usually means you are running `make` in a read-only syzkaller checkout. Use a writable working copy as shown above, or run builds as a user that can write to the checkout.

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
