# Enumerating Python public symbols from the source file

The required-symbol checklist for a Python→Scala translation comes from
the **Python source file**, not from the task statement's example list.
This chapter is the authority for workflow step 1 whenever the task
statement contains a parenthesized or inline class/function list, OR
you are tempted to drop a Python class because the task did not name it.

**Observed failure (iter_3).** A task statement said "must have all
classes and functions in the python code" followed by a parenthesized
list of thirteen named symbols. The Python source actually contained
twenty-three public classes. The agent read the parenthesized list as
exhaustive and silently dropped ten classes (`MutableTokenBatch`,
`TokenContainer`, `TokenSink`, `BivariantHandler`, `TokenRegistry`,
`TokenFunctor`, `TokenMonad`, `JsonTokenizer`, `HasLength`,
`TokenProcessor`) from the Scala output. The agent's own justification
was that the parenthetical "i.e." list was enumerative. The grader
checked the dropped symbols; the task scored 0.

The failure is distinct from the axis-pick failure: even on a correctly-
chosen pole (a) the agent still would have dropped these classes under
the exhaustive-list reading.

---

## 1. Open-list vs closed-list wording

Classify the task statement's symbol list before trusting it:

| Wording in the task statement | List kind | Required set |
|---|---|---|
| "must have all classes and functions in the python code" | **open** | every public symbol in the Python file |
| "every class", "all classes", "all public symbols" | **open** | every public symbol in the Python file |
| "i.e. X, Y, Z" / "e.g. X, Y, Z" / "including X, Y, Z" | **open** | every public symbol in the Python file; the list is examples |
| bare parenthesized list after any open-set phrase | **open** | every public symbol in the Python file |
| "only the following classes: X, Y, Z" | **closed** | exactly `{X, Y, Z}` |
| "exactly these classes: X, Y, Z" | **closed** | exactly `{X, Y, Z}` |
| "limited to X, Y, Z" / "no other classes" | **closed** | exactly `{X, Y, Z}` |
| no list at all | **open** | every public symbol in the Python file |

**Default assumption on ambiguity: open.** Dropping a class that was
required costs the task; adding a class that was not required costs
nothing (unless the task explicitly bans extras, which is closed-list
wording and is covered above).

---

## 2. Grep recipe — enumerate every public top-level symbol

```python
# Enumerate every public top-level symbol in the Python source file.
# Run this once, in the shell, before writing any Scala plan.
#
#   grep -nE '^class |^def |^[A-Z_][A-Z_0-9]* = ' <python-file>
#
# Breakdown of the three patterns:
#   ^class            — top-level class definition
#   ^def              — top-level function definition
#   ^[A-Z_][A-Z_0-9]* = — top-level SCREAMING_CASE constant / sentinel
#
# Private names start with `_` and are excluded by the capital-letter
# anchor in the third pattern. For classes/functions, inspect each hit:
# a leading underscore (`class _Foo`, `def _bar`) means private — skip.

import subprocess, re

def enumerate_public_symbols(python_file: str) -> list[str]:
    out = subprocess.check_output(
        ["grep", "-nE", r"^class |^def |^[A-Z_][A-Z_0-9]* = ", python_file],
        text=True,
    )
    symbols = []
    for line in out.splitlines():
        # line looks like "42:class Foo(Base):"
        _, _, rest = line.partition(":")
        m = re.match(r"^(?:class|def)\s+(\w+)", rest)
        if m and not m.group(1).startswith("_"):
            symbols.append(m.group(1))
            continue
        m = re.match(r"^([A-Z_][A-Z_0-9]*)\s*=", rest)
        if m:
            symbols.append(m.group(1))
    return symbols
```

For nested classes inside outer classes (common in Python modules that
expose inner enums or helper dataclasses), extend the pattern to match
indentation levels one layer deep as well:

```bash
# Also catches `    class Inner(...):` (4-space indent)
grep -nE '^(class |def |    class |    def |[A-Z_][A-Z_0-9]* = )' <python-file>
```

Only promote nested names to the Scala plan when the Python source
re-exports them (`__all__`, `from .module import Inner`) or when the
task statement names them.

---

## 3. Build the checklist and tick off counterparts

For each symbol returned by step 2, add a row to the plan:

```
Symbol             | Kind       | Scala counterpart file / section | Status
-------------------|------------|---------------------------------|--------
TokenType          | Enum       | Output.scala §1 TokenType       | [ ]
Token              | class      | Output.scala §2 Token           | [ ]
BaseTokenizer      | class      | Output.scala §3 BaseTokenizer   | [ ]
...
MutableTokenBatch  | class      | Output.scala §N MutableTokenBatch | [ ]
TokenRegistry      | class      | Output.scala §N+1 TokenRegistry | [ ]
HasLength          | Protocol   | Output.scala §N+2 HasLength     | [ ]
```

A row without a counterpart file/section is a **dropped-class
divergence** — do not mark the plan complete while any row is unticked.
The grader's call site for a dropped class fails identifier lookup
regardless of how clean the kept symbols are.

### Branch — what to do with each Python kind

```python
# Branch A: Python class (concrete or ABC) — becomes a Scala class/trait
#           preserving the public API shape per `preserve-python-api.md`.
# Branch B: Python Protocol / typing.Protocol — becomes a Scala trait
#           (structural type) or a type class, depending on pole.
# Branch C: Python Enum — becomes `scala.Enumeration` / Scala-3 `enum`
#           on pole (a), with member names verbatim.
# Branch D: Python top-level function — becomes a method on a `package
#           object` or a Scala `object`.
# Branch E: Python top-level SCREAMING_CASE constant / sentinel — becomes
#           a Scala `val` on an `object`, name preserved verbatim.
```

---

## 4. Worked example — iter_3 recurrence

**Task statement (quoted):** "The Scala translation must have all
classes and functions in the python code (i.e. `TokenType`, `Token`,
`BaseTokenizer`, `StringTokenizer`, `NumericTokenizer`,
`TemporalTokenizer`, `UniversalTokenizer`, `WhitespaceTokenizer`,
`TokenizerBuilder`, `tokenize`, `tokenizeBatch`, `toToken`,
`withMetadata`)."

**Wrong reading:** the parenthetical "i.e." list is exhaustive; only
these 13 names are required. (This is the iter_3 agent's reading.)

**Correct reading:** "all classes and functions in the python code" is
open-list wording; the "i.e." parenthetical gives examples; every
public symbol in the Python file is required.

**Step 2 output (hypothetical) — the Python source has 23 public
symbols:**

```
TokenType, Token, BaseTokenizer, StringTokenizer, NumericTokenizer,
TemporalTokenizer, UniversalTokenizer, WhitespaceTokenizer, JsonTokenizer,
TokenizerBuilder, MutableTokenBatch, TokenContainer, TokenSink,
BivariantHandler, TokenRegistry, TokenFunctor, TokenMonad, HasLength,
TokenProcessor, tokenize, tokenizeBatch, toToken, withMetadata
```

The 13 in the task statement are a subset; the other 10 are the ones
iter_3 dropped. All 23 must appear in the Scala output.

---

## 5. Verification

```python
# After writing Output.scala, confirm every row of the step-3 checklist
# has a counterpart section. Grep the Scala file for each symbol name:
#
#   for sym in $(grep -oE '^(class|def) \w+' <python-file> | awk '{print $2}'); do
#       grep -q "\\b$sym\\b" Output.scala || echo "MISSING: $sym"
#   done

import subprocess

def verify_counterparts(python_file: str, scala_file: str) -> list[str]:
    symbols = enumerate_public_symbols(python_file)
    scala_src = open(scala_file).read()
    missing = [s for s in symbols if s not in scala_src]
    return missing
```

### Corrective step on failure

If `verify_counterparts(...)` returns a non-empty list, each listed
symbol is a dropped-class divergence:

1. For each missing symbol, go back to the Python source and read its
   definition (per workflow step 1 EOF confirmation).
2. Add a counterpart section to `Output.scala`. Preserve the Python name
   verbatim (even if idiomatic Scala would camel-case it — see
   `preserve-python-api.md` §4).
3. Re-run `verify_counterparts`. Repeat until the list is empty.
4. Do **not** submit while any symbol is missing. "The grader didn't
   explicitly ask for this class" is not a valid justification when the
   task used open-list wording; see §1 above.

If a symbol is missing because the Python source defines it with a
leading underscore (`class _Internal(...)`), it is private — skip it
and record the skip in the plan with a one-line justification ("private
by Python convention — leading underscore").
