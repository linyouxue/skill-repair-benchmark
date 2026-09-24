# Triage `make descriptions` failures

Use this when syzlang compilation errors cascade or the reported error is not obviously actionable.

## 1) Categorize the first error (runtime branch)

```python
import re

def classify(err: str) -> str:
    rules = [
        (r"unknown type", "unknown_type"),
        (r"undefined reference", "missing_reference"),
        (r"defined for none of the arches", "const_arch_scope"),
        (r"cannot find include file", "missing_include"),
        (r"unexpected token|syntax error", "syntax"),
    ]
    for pat, label in rules:
        if re.search(pat, err, re.IGNORECASE):
            return label
    return "other"

err = "unknown type foo"
kind = classify(err)
print(kind)
```

## 2) Corrective actions by category

- **unknown_type**: define the type before first use, or import/inline an existing type definition used elsewhere.
- **missing_reference**: ensure the file that defines the referenced type/resource is included/visible in the build; otherwise move the definition into the current file.
- **const_arch_scope**: add the constant to the matching `.const` file and ensure `arches = ...` includes the architecture(s) you build for.
- **missing_include**: fix the include path or prefer manual `.const` when extraction depends on unavailable headers.
- **syntax**: reduce to the smallest line that fails; compare against a known-good idiom found in `sys/linux/*.txt`.

Verification:
- After applying the category’s fix, rerun `make descriptions`. If the *same* first error remains, undo speculative changes and instead create a minimal repro by commenting out new blocks until the error disappears; then reintroduce lines one-by-one.
