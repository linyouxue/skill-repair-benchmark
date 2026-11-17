# Ioctl coverage reconciliation from a UAPI header

Use this when a task says “describe all ioctls from <header>” and/or provides an explicit total (e.g., “N total”). The goal is to prevent silent under-coverage caused by filtering (e.g., skipping `OBSOLETE__*`) without permission.

## Procedure (enumerate → implement → verify)

### 1) Enumerate symbols from the header
- Identify how ioctls are declared: usually `#define NAME _IO*('X', NR, TYPE)` plus possible wrappers like `OBSOLETE__IOR/IOW/...`.
- Produce a literal list of macro names that are part of the interface.

Runnable helper (works on a saved header file):

```python
import re
from pathlib import Path

hdr = Path("/path/to/header.h").read_text(errors="ignore")

# Capture both direct _IO* uses and wrapper macro invocations.
pat = re.compile(r"^\s*#\s*define\s+(\w+)\s+.*\b(_IO|_IOR|_IOW|_IOWR)\s*\(", re.M)

names = sorted(set(m.group(1) for m in pat.finditer(hdr)))
print("count:", len(names))
print("\n".join(names))
```

Runtime branch:
- If the count is **lower than expected**, broaden the regex to include project-specific wrappers (e.g., `OBSOLETE__IOR`, `__IOW`, etc.), or fall back to manual review around `#define` blocks.
- If the count is **higher than expected**, filter by prefix / section (e.g., only `PP*`), but document the filter and confirm it matches the prompt’s scope.

### 2) Implement: map each macro to one `ioctl$...` line
For each macro:
- Set direction from `_IOR/_IOW/_IOWR`.
- Map the macro’s TYPE argument to a syzlang type (struct or scalar pointer).
- Ensure the `.const` file defines every constant referenced by `const[...]`.

### 3) Verify coverage against the written syzlang
Given your written `dev_xxx.txt`, validate that every header macro name appears as a command constant.

```python
import re
from pathlib import Path

header_names = Path("header_names.txt").read_text().splitlines()
syz = Path("/path/to/dev_xxx.txt").read_text(errors="ignore")

# Collect const[...] tokens (common for ioctl cmd constants).
cmds = set(re.findall(r"const\[([A-Za-z0-9_]+)\]", syz))
missing = [n for n in header_names if n not in cmds]

print("expected:", len(header_names))
print("found:", len(cmds))
print("missing:", missing)

assert not missing, "coverage check failed"
```

Runtime branch:
- If many are missing because your `.txt` uses renamed constants, choose one:
  - **Rename** syzlang `const[...]` to match header macros (best for strict diff tasks).
  - Or **record a mapping table** and re-run the verification using that mapping.

### 4) Verification step + corrective action
If the assertion fails:
1. Add the missing ioctl entries (or rename constants) so each header macro is represented.
2. Re-run the coverage check until `missing` is empty.
3. Only then run `make descriptions` to ensure the file compiles.
