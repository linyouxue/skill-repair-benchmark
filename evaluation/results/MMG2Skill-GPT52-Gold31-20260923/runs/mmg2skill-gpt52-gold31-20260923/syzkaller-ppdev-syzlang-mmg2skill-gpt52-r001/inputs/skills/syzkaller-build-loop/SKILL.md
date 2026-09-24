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
# 4. Build syzkaller (use explicit target when requested)
make all TARGETOS=linux TARGETARCH=amd64
```
### If `/opt/syzkaller` is not writable for build outputs
If `make descriptions`/`make all` fails due to permission errors creating build artifacts (e.g., `./bin`), run the build in a writable copy **but keep the source-of-truth files in** `/opt/syzkaller`:
```bash
cp -a /opt/syzkaller /home/$USER/syzkaller-build
cd /home/$USER/syzkaller-build
make descriptions
make all TARGETOS=linux TARGETARCH=amd64
# Confirm the built-copy files match /opt before finishing
diff -u /opt/syzkaller/sys/linux/your_file.txt sys/linux/your_file.txt
diff -u /opt/syzkaller/sys/linux/your_file.txt.const sys/linux/your_file.txt.const
```
## Quick Rebuild (After Minor Edits)
If you only changed descriptions (not constants):
```bash
cd /opt/syzkaller
make descriptions   # Runs syz-sysgen to compile descriptions
```
If you add new constants, update the `.const` file first.
## Basic Content Sanity Checks (before/after build)
Examples:
```bash
# Count ioctl declarations in the new description file
grep -n '^ioctl' sys/linux/your_file.txt | wc -l
# Confirm key required lines exist in the source .txt (not in generated artifacts)
grep -n 'resource fd_' -n sys/linux/your_file.txt
grep -n 'syz_open_dev' -n sys/linux/your_file.txt
```
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
