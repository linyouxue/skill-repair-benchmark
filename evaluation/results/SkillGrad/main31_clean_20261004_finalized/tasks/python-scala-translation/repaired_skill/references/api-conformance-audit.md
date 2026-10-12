# API Conformance Audit for Python → Scala Translations

Use this procedure when the grader may check for **exact public names/signatures** (reflection, imports, or prompt lists). The goal is to prevent “idiomatic rewrites” from drifting away from the required API surface.

## 1) Build the required-surface checklist

Create two sets:

- **Prompt-required names**: every class/function/constant explicitly listed.
- **Python public surface**: every top-level def/class plus any protocol/abstract methods that callers rely on.

Then unify them into a single checklist: `(name, kind, signature/shape, where it lives)`.

### Runnable helper (parse Python for public defs/classes)

```python
import ast
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class Pub:
    kind: str  # 'class' | 'function'
    name: str

def public_surface(py_src: str) -> List[Pub]:
    t = ast.parse(py_src)
    out: List[Pub] = []
    for node in t.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
            out.append(Pub('function', node.name))
        if isinstance(node, ast.ClassDef) and not node.name.startswith('_'):
            out.append(Pub('class', node.name))
    return out

# Branch: provide either file text or an in-memory string
py_text: Optional[str] = None
if py_text is None:
    py_text = """\
class A: pass

def f():
    return 1
"""

print(public_surface(py_text))
```

## 2) Decide on naming strategy (runtime branch)

**Branch A — exact names required (common in graders):**
- Implement every required member with **exact spelling**.
- If Scala conventions differ (snake_case vs camelCase), add an alias that delegates.

**Branch B — free to redesign:**
- Prefer idiomatic Scala naming; keep a thin compatibility layer only if needed.

## 3) Implement aliases safely (don’t duplicate logic)

Rule: **one implementation, many entrypoints**.

Example pattern:

- Put logic in one method (`impl`).
- Expose required name(s) calling `impl`.
- Expose optional idiomatic alias also calling `impl`.

## 4) Pre-submit verification

Perform these checks before finalizing:

1. **No placeholders**: search for `TODO`, `???`, `REDACTED`.
2. **All checklist items present**: every required name exists in the final Scala.
3. **Signature sanity**: constructors/methods accept the same kinds of inputs as Python (including “optional”/`None` cases).

### Verification action on failure

- If (1) fails: replace placeholders with real implementations or remove the feature entirely.
- If (2) fails: add missing members *as delegating wrappers* (avoid new logic).
- If (3) fails: adjust types to be at least as permissive as Python at the boundary (e.g., accept `Any`/`Object` at the public edge, validate inside), then re-run (1)–(3).

### Minimal “presence audit” script (heuristic)

```python
import re

def missing_required(scala_src: str, required_names: list[str]) -> list[str]:
    # Heuristic: looks for word-boundary occurrences of names.
    # Good enough to catch accidental renames before submission.
    return [n for n in required_names if not re.search(rf"\b{re.escape(n)}\b", scala_src)]

scala_text = """
trait X { def to_token(): String }
object X { def toToken(): String = "" }
"""
required = ["to_token", "toToken"]
miss = missing_required(scala_text, required)

# Branch: enforce failure fast vs print report
if miss:
    raise SystemExit(f"Missing required names: {miss}")
print("API presence audit passed")
```
