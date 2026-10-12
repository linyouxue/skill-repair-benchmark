# Translation conformance gates (Python → Scala)

Use this checklist when translating for a **hidden grader** or when the requirement is “Scala does the same thing as the Python one”. Compilation and name-presence checks are necessary but not sufficient.

## Gate 1 — Placeholder/stub ban (mechanical)

**Goal:** ensure there is no non-executable surface left behind.

Search the full Scala artifact(s) for placeholder tokens and obvious stubs:
- tokens: `TODO`, `???`, `REDACTED`
- suspicious bodies: `return null`, `return Nil`, `return Map.empty`, `throw new NotImplementedError` (allowed only if Python also throws)

### Runnable scan

```python
import re
from dataclasses import dataclass

@dataclass
class ScanHit:
    line: int
    text: str

PLACEHOLDER_RE = re.compile(r"\b(TODO|\?\?\?|REDACTED)\b")
STUB_RE = re.compile(r"\b(return\s+null|return\s+Nil|return\s+Map\.empty|NotImplementedError)\b")

def scan_scala(scala_src: str) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for i, line in enumerate(scala_src.splitlines(), start=1):
        if PLACEHOLDER_RE.search(line) or STUB_RE.search(line):
            hits.append(ScanHit(i, line.rstrip()))
    return hits

scala_text = """
object X {
  def f(x: Int): Int = ???
}
"""

hits = scan_scala(scala_text)
# Branch: fail fast vs emit report
fail_fast = True
if hits and fail_fast:
    raise SystemExit("Found placeholders/stubs:\n" + "\n".join(f"{h.line}: {h.text}" for h in hits))
print("scan ok" if not hits else hits)
```

**Corrective action on failure:** replace each placeholder with executable code. If you are short on time, implement minimally-correct delegating wrappers (aliases) that call the canonical implementation.

## Gate 2 — Contract inventory (API conformance)

**Goal:** match the public surface the grader imports/calls.

1. Enumerate **prompt-required names**.
2. Enumerate the **Python public surface** (top-level defs/classes; plus required methods/protocols).
3. Unify into one checklist: `(name, kind, shape/signature, location)`.

Read `references/api-conformance-audit.md` for a helper that extracts public defs/classes.

**Corrective action on failure:** add missing items as delegating wrappers; avoid adding new logic unless required.

## Gate 3 — Behavior spot-check harness (parity)

**Goal:** catch drift on inputs hidden tests often exercise.

Pick a small set of representative inputs for each major behavior, including:
- null/None-ish values
- empty vs non-empty strings/collections
- numeric formatting/precision edges
- tokenization / whitespace / punctuation boundaries
- validation and error raising behavior

### Runnable harness skeleton

```python
from dataclasses import dataclass

@dataclass
class Case:
    name: str
    inp: object
    expected: object

cases = [
    Case("example", inp="", expected=""),
]

# Branch: stop on first failure vs collect failures
stop_early = False
failures: list[str] = []

for c in cases:
    got = c.inp  # replace with call into a wrapper that runs Scala or a ported oracle
    if got != c.expected:
        msg = f"{c.name}: expected={c.expected!r} got={got!r}"
        if stop_early:
            raise AssertionError(msg)
        failures.append(msg)

if failures:
    raise AssertionError("Behavior spot-check failed:\n" + "\n".join(failures))
print("behavior spot-check passed")
```

**Corrective action on failure:** identify whether the mismatch is (a) boundary typing/null handling, (b) formatting, (c) parsing/tokenization rules, or (d) validation/exception semantics; then adjust Scala to match Python’s observable behavior and re-run Gate 1–3.

## Gate 4 — Finalize

Only finalize after all gates pass:
- Placeholder/stub scan clean
- Contract checklist satisfied
- Spot-check harness shows expected results
