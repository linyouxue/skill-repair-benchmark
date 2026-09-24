# Choosing ioctl argument representation and pointer direction

Use this when translating a C ioctl prototype to syzlang and you are unsure whether to use `intptr[...]` vs `ptr[...]`, or whether the pointer is `in`, `out`, or `inout`.

## 1) Map C signature to a syzlang arg (runtime branch)

```python
def classify_ioctl_arg(c_arg: str) -> str:
    c = c_arg.replace("const ", "").strip()

    # Runtime branches
    if "*" not in c:
        return "value"            # typically intptr/int32/etc.
    if c.startswith("void*") or c.startswith("char*"):
        return "buffer_ptr"       # ptr[in/out, array[int8]] etc.
    return "typed_ptr"            # ptr[in/out, struct_type]

# Examples
for ex in ["int cmd", "struct foo *arg", "void *arg"]:
    print(ex, "->", classify_ioctl_arg(ex))
```

## 2) Decide direction from kernel behavior

- **Branch A (kernel reads user memory only):** `ptr[in, T]`
- **Branch B (kernel writes user memory only):** `ptr[out, T]`
- **Branch C (kernel reads then writes):** `ptr[inout, T]`
- **Branch D (not a pointer in C):** use `intptr[...]`/`int32`/`int64` etc.

## 3) Verification and corrective action

Verification:
- After writing the syzlang line, run `make descriptions`.
  - If you get a type error (`unknown type`), define the struct/resource earlier or reuse an existing type from another file.
  - If you get constant errors (`defined for none of the arches`), add/adjust the `.const` file and rerun.
  - If it compiles but the ioctl shape seems wrong, go back to the kernel header/docs and confirm whether the ioctl argument is a pointer, what it points to, and whether fields are in/out; then update `ptr[...]` direction accordingly.
