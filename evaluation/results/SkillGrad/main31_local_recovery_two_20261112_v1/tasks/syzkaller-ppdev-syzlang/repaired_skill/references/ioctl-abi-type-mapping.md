# Ioctl ABI type mapping (C → syzlang)

Use this when an ioctl macro’s TYPE argument is a C scalar or pointer type and you’re unsure how to model it in syzlang.

## Core rule
Prefer ABI-safe, width-stable representations when the C type’s size varies by architecture (`int`, `long`, pointers). Avoid unjustified narrowing to `int32/uint32` unless the ABI contract is explicit for the target arches.

## Quick mapping table (default-first)
- `int` / `unsigned int`: `intptr` (by value) or `ptr[in/out, intptr]` (by pointer)
- `long` / `unsigned long`: `intptr` (Linux LP64/ILP32 varies)
- pointers to scalars (e.g., `int*`): `ptr[in/out, intptr]`
- `__u32` / `uint32_t` / `u32`: `int32` or `flags[..., int32]` only if semantics are signed, else `flags[..., int32]` with careful constraints; when in doubt, keep as `intptr` unless you can confirm it is fixed-width
- `__u64` / `uint64_t` / `u64`: `int64` / `uint64` equivalents if available in the dialect, otherwise model as a struct of two `int32` or use an existing canonical type from syzkaller’s library
- structs: model as a `struct { ... }` with fields matching the UAPI definition (use existing syzkaller types when available)

## Worked procedure with branches

### Step 1: Decide if the type is ABI-varying
- If it is `int`, `unsigned int`, `long`, `size_t`, or any pointer: treat as ABI-varying.
- Else if it’s `__u32/__u64` or a named struct: treat as ABI-stable.

### Step 2: Choose syzlang representation

Runnable helper to sanity-check a set of ioctl macro lines (illustrative):

```python
import re

ioctls = [
    ("IOCTL_A", "int"),
    ("IOCTL_B", "unsigned int"),
    ("IOCTL_C", "struct foo"),
]

def classify(c_type: str) -> str:
    c_type = c_type.strip()
    if re.search(r"\b(int|unsigned int|long|unsigned long|size_t)\b", c_type):
        return "abi_varying"
    if "*" in c_type:
        return "abi_varying"
    return "abi_stable"

for name, c_type in ioctls:
    cls = classify(c_type)
    if cls == "abi_varying":
        syz = "ptr[inout, intptr]"  # adjust direction separately
    else:
        syz = "ptr[inout, some_struct]"
    print(name, c_type, "->", syz)
```

Runtime branch:
- If you later discover the kernel expects a fixed-width type (e.g., docs say `u32`): switch to `int32/uint32` modeling and update the `.const`/structs accordingly.
- If the checker appears to require a specific style (strict diff): match existing syzkaller descriptions in the tree for similar ioctls and conform.

## Verification step + corrective action
After modeling, validate consistency:
1. Ensure `_IOR/_IOW/_IOWR` direction matches `ptr[out/in/inout]`.
2. Ensure the modeled payload width can hold the C type on every target arch.

If a build or diff fails due to type mismatches:
- First, search the syzkaller tree for similar ioctl macros and copy the canonical modeling pattern.
- If still ambiguous, fall back to `intptr` for ABI-varying scalars (it is usually the safest cross-arch choice).
