---
name: python-scala-idioms
description: Translate Python to Scala while preserving required public APIs, using idioms only when they do not change observable behavior or required names.
---

# Python → Scala Translation: Idioms (With API Fidelity)

## Plan: translate against a contract, then refactor

1. **Lock the target surface first**: list required public members (prompt + Python module) and treat them as a contract.
2. **Translate behavior before refactoring**: get a minimal, faithful Scala version working before adding Scala-idiomatic reshaping.
3. **Prefer “local idioms”** (e.g., `Option`, `match`) that don’t change the API surface or semantics.
4. **When naming/casing conflicts exist**, keep the required name and add a delegating alias for the idiomatic one.
5. **Before finalizing**, do an API-surface sweep: confirm every contract item exists *and has executable code* (not just a signature).

```scala
// One implementation, multiple entrypoints (aliases)
trait Api {
  def required_name(x: Int): Int
  final def requiredName(x: Int): Int = required_name(x)
}
```

Read references/api-conformance-audit.md when the prompt or tests likely check for exact public names/signatures.
Skip when you are free to redesign the API (no reflective tests, no “keep names” requirement).

## Pre-submit gates: no placeholders + conformance audit

Before finalizing a translation, enforce two gates:

1. **No placeholders/stubs anywhere in Scala**: scan the whole artifact for banned stub tokens (e.g., `TODO`, `???`, `REDACTED`) and obvious stub bodies, and refuse to submit until zero matches remain.
2. **API + behavior audit**: verify that every contract item exists (prompt + Python public surface) and spot-check behavior on representative/edge inputs.

```python
# Lightweight pre-submit scan (runs fast; catches silent stubs)
import re

def assert_no_placeholders(scala_src: str) -> None:
    bad = re.findall(r"\b(TODO|\?\?\?|REDACTED)\b", scala_src)
    if bad:
        raise AssertionError(f"placeholders found: {sorted(set(bad))}")

# Branch: enforce strict failure vs report-only
strict = True
if strict:
    assert_no_placeholders(scala_src="")
else:
    try:
        assert_no_placeholders(scala_src="")
    except AssertionError as e:
        print(e)
```

Read references/translation-conformance-gates.md when you are translating for a hidden grader or parity tests.
Skip when you are producing an illustrative snippet where stubs are acceptable.

## Immutability first (when semantics allow)

```python
# Python - mutable by default
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1
        return self.count
```

```scala
// Scala - immutable approach
case class Counter(count: Int = 0) {
  def increment: Counter = copy(count = count + 1)
}

val c2 = Counter().increment
```

## Expression-based style

```python
# Python
def status(code):
    if code == 200:
        return "OK"
    return "Other"
```

```scala
// Scala
def status(code: Int): String =
  if (code == 200) "OK" else "Other"
```

## Prefer pattern matching over if/else chains

```python
# Python
if x == 0:
    out = "zero"
else:
    out = "nonzero"
```

```scala
// Scala
val out = x match {
  case 0 => "zero"
  case _ => "nonzero"
}
```

## None/null handling: use Option for internal logic

```python
# Python
return value if value is not None else default
```

```scala
// Scala
val out = Option(value).getOrElse(defaultValue)
```

## Scala naming conventions (only when allowed)

- Scala typically prefers `camelCase` methods.
- If the task requires preserving `snake_case` names from Python, **define those exact methods** and optionally add `camelCase` aliases.

```scala
trait Api2 {
  def required_name(x: Int): Int
  final def requiredName(x: Int): Int = required_name(x)
}
```

## Common pitfalls

- Doing an “idiomatic rewrite” before confirming the required public API exists and matches names/signatures.
- Renaming required members (e.g., snake_case ↔ camelCase) without adding explicit, tested aliases.
- Adding unrelated infrastructure (extra ADTs/wrappers/registries) that increases semantic drift and test risk.
- Shipping code that compiles but still contains placeholders/stubs (`TODO`, `???`, redactions) or empty delegations.
