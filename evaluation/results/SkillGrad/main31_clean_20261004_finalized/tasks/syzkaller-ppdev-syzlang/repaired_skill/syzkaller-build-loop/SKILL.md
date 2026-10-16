---
name: syzkaller-build-loop
description: Iterate on syzkaller syscall descriptions by editing syzlang files, supplying constants, compiling descriptions, rebuilding, and verifying outcomes with a repeatable loop.
---

# Planning / Workflow

## Final-turn lint (user-facing completion)

Treat the final message as a hard gate: right before sending it, ensure it contains no meta/template scaffolding and instead reads as the actual completion (Changes / Verification / Limits).

```python
final_text = draft_response
banned = ["Finish with message", "Summary:", "TODO", "template", "placeholder"]
if any(s in final_text for s in banned):
    raise ValueError("Meta/template detected in final response; rewrite as user-facing completion")

lower = final_text.lower()
has_changes = any(w in lower for w in ["created", "updated", "changed", "added"])
has_verification = any(w in lower for w in ["verified", "verification", "ran ", "make ", "tested"])
if not (has_changes and has_verification):
    raise ValueError("Final response missing changes and/or verification; add both")
```

Read references/final_turn_lint.md when you are about to send the last message (especially after drafting, outlining, or using a template). Skip when the final response is already a clean confirmation.

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
