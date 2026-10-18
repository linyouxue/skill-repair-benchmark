# Picking the API-shape ↔ idiomatic-Scala axis from the task statement

Python→Scala translation tasks live on an axis with two opposing poles:

- **Pole (a) — Preserve the Python public API shape.** The evaluator calls
  the Scala using Python names, Python-accepted argument types, and Python
  return types. Idiomatic rewrites (sealed-ADT wrappers around union-typed
  params, `Try`/`Either` wrapping of raw returns, function-returning in
  place of raw returns, `(String, Any)*` varargs for `**kwargs`, hand-
  rolled sealed-trait enums, parametric `[A: Numeric]`,
  `snake_case`→`camelCase` renames, enum member identifier renames from
  `STRING` to `String`, dropping Python classes not named in a task-
  statement example list, mid-task paradigm swaps) break evaluator call
  sites.
- **Pole (b) — Idiomatic Scala for a "proficient Scala developer".** The
  grader penalizes word-to-word translations. Bounded generics / sealed
  ADTs / type classes are expected in place of `Any` + `isinstance`-style
  match; `Try`/`Either` in place of thrown `IllegalArgumentException`;
  persistent immutable builders in place of `mutable.ListBuffer` + `var`;
  `UpperCamelCase` enum members per Scala convention; locale-safe
  formatting.

**The axis-choice step is mandatory**: both poles are correct for different
tasks and neither is correct by default. Choose BEFORE writing Scala. The
four observed failure modes are:

- iter_0: defaulting to pole (b) when the task demanded pole (a).
- iter_1: defaulting to pole (a) when the task demanded pole (b).
- iter_2: **recurrence of iter_0** — defaulting to pole (b) on a task that
  listed named public APIs verbatim and said "same classes/functions as
  the Python source" and "do the same thing".
- iter_3: **second recurrence** — the required-artifact template was
  present in L2 but the agent did not emit it; chose "mixed, strongly
  leaning (b)" on a task whose signals were pole (a) ("must have all
  classes and functions in the python code", thirteen named APIs listed).
  Compound divergences: wrapper ADTs (`StringLike`, `NumericValue`,
  `TemporalValue`), enum member rename (`STRING` → `String`),
  function-returning builder (`T => Either[String, Token]`),
  `(String, Any)*` varargs, ten classes dropped.

**Defensive rule — ambient tone vs signal phrases.** The skill files lead
with "idiomatic Scala", "proper abstractions", "proficient developer"
framing. That tone is correct **on pole (b)** and misleading **on
pole (a)**. The axis is not decided by tone or by what feels Scala-shaped
— it is decided by concrete signal phrases from the task statement.

---

## 1. Required artifact — write before any Scala

Before writing any Scala, write exactly these four lines at the top of
your plan. If any line is empty, the axis is not pinned — re-read the
task statement:

```
Named public APIs (verbatim from the task): <list of class/method names>
Signal phrase (verbatim quote from the task): "<quote>"
Chosen pole: (a) | (b) | mixed
Raw-type evaluator call sites (derived from the named APIs AND exercising
at least one API per class in the Python source, using ONLY Python-shaped
types — no wrapper ADTs, no `.get` on `Try`, no `.right.get` on `Either`,
no translator-defined helpers):
  1. <call site 1>
  2. <call site 2>
  3. <call site 3>
```

A snippet that uses your own wrapper ADT (`StrOrBytes.Str("hi")`,
`StringLike.Str("hi")`, `TemporalValue.DateTime(...)`,
`NumericValue.IntVal(3)`), calls `.get` on a `Try` return, calls
`.right.get` on an `Either` return, or constructs translator-defined
helper objects is **not** a raw-type call-site snippet. The call sites
must look as the evaluator would write them, in Python-call-site style,
using plain Scala/JVM primitives (`"hello"`, `LocalDate.now()`, `42`,
`List(...)`, named kwargs, Python enum identifiers verbatim like
`TokenType.STRING`).

---

## 2. Signal phrases — grep the task statement first

### Pole (a) signals — "preserve the API"

- "same classes/functions as the Python source"
- "must have all classes and functions in the python code" (open-list;
  see also `references/enumerate-python-symbols.md`)
- "do the same thing" / "must do the same thing"
- named public APIs listed in the task statement (method names, class
  names, field names appear verbatim; e.g. `tokenize`, `tokenizeBatch`,
  `toToken`, `withMetadata`)
- "preserve the Python public API"
- "same signatures" / "match these signatures"
- "match this call site" or an evaluator script quoted with raw Python
  types (`obj.method("abc")`, `obj.method(3)`, `obj.method(datetime(...))`)
- keyword constructor arguments shown in `snake_case`
  (`Cls(format_str="...")`, `Cls(format_options={...})`)
- the task shows a Python test file or Python invocation examples
- enum members referenced by SCREAMING_CASE identifier
  (`TokenType.STRING`, `Color.RED`)

### Pole (b) signals — "idiomatic Scala"

- "proficient Scala developer" / "experienced Scala developer"
- "idiomatic Scala"
- "should not be a word-to-word translation"
- "proper abstractions for representing data"
- "handle errors and exceptions naturally in Scala"
- "use the Scala type system"
- "immutable" / "immutability"
- "Scala naming conventions" / "follow Scala conventions"
- no evaluator snippet, no Python call-site example, no `snake_case` kwargs

### Mixed case

If BOTH sets of signals are present (the task names some public symbols
AND asks for idiomatic Scala), satisfy pole (a) at the **public API
boundary** and pole (b) in the **internal implementation**:

```scala
// Public method accepts raw Python types AND returns a raw Python
// return type (pole a):
class StringTokenizer {
  def tokenize(value: Any): Token = value match {
    // but delegate immediately to type-class-dispatched internals (pole b):
    case s: String      => Tokenize[String].run(s)
    case b: Array[Byte] => Tokenize[Array[Byte]].run(b)
    case other => throw new IllegalArgumentException(s"Unsupported: $other")
  }
}
// Internal `Tokenize[T]` is a sealed/type-class hierarchy; externally
// visible class name, parameter name, accepted argument types, AND
// return type still match Python.
```

---

## 3. Decision procedure (run before any Scala is emitted)

```python
# Pseudocode of the axis-choice step
pole_a_hits = count_signals(task_statement, POLE_A_SIGNALS)
pole_b_hits = count_signals(task_statement, POLE_B_SIGNALS)

if pole_a_hits > 0 and pole_b_hits == 0:
    axis = "a"      # preserve API shape
elif pole_b_hits > 0 and pole_a_hits == 0:
    axis = "b"      # idiomatic Scala
elif pole_a_hits > 0 and pole_b_hits > 0:
    axis = "mixed"  # pole (a) boundary, pole (b) internals
else:
    # No signals either way — default to pole (a) when an evaluator
    # script with raw Python types is shown OR named public APIs are
    # listed; otherwise default to pole (b).
    axis = "a" if task_shows_python_call_sites_or_named_apis else "b"

print(f"Chosen axis: {axis}; proceeding with the matching rules.")
```

**Verification of the axis choice**: the required-artifact template in §1
is the verification. If you cannot quote a concrete signal phrase from
the task, the axis is not pinned — re-read.

**Branch — if axis = "a"**: follow `references/preserve-python-api.md` in
full (nine divergence classes: §1 ADT wrappers, §2 runtime dispatch, §3
constructor params, §4 renames, §5 paradigm swaps, §6 return-type
wrapping including function wrapping, §7 kwargs, §8 enum structure, §9
enum member names). Enumerate every class in the Python source per
`references/enumerate-python-symbols.md` — task-statement example lists
are non-exhaustive.

**Branch — if axis = "b"**: follow
`references/scala-generics-for-python-typevars.md` in full. Bounded
generics / sealed ADTs / type classes / union types for Python TypeVars;
`Try`/`Either` for errors; persistent immutable builders; `UpperCamelCase`
enum members; `Locale.ROOT` on numeric formatting.

**Branch — if axis = "mixed"**: run the pole-(b) checklist on the internal
representation and the pole-(a) checklist on the public boundary. The public
class name, public method signatures, keyword-argument names, enum member
identifiers, and **return types** come from the Python source; everything
delegate-to is yours.

---

## 4. Worked example — pole (a) (derived from iter_2/iter_3 recurrence)

**Task statement (quoted):** "The Scala translation must have all
classes and functions in the python code (i.e. `TokenType`, `Token`,
`BaseTokenizer`, `StringTokenizer`, `NumericTokenizer`,
`TemporalTokenizer`, `UniversalTokenizer`, `WhitespaceTokenizer`,
`TokenizerBuilder`, `tokenize`, `tokenizeBatch`, `toToken`,
`withMetadata`) and do the same thing."

**Required artifact:**

```
Named public APIs (verbatim from the task):
  TokenType, Token, BaseTokenizer, StringTokenizer, NumericTokenizer,
  TemporalTokenizer, UniversalTokenizer, WhitespaceTokenizer,
  TokenizerBuilder, tokenize, tokenizeBatch, toToken, withMetadata
  (plus any additional classes in the Python source — the "i.e." list
   is non-exhaustive; see `references/enumerate-python-symbols.md`)
Signal phrase (verbatim quote from the task):
  "must have all classes and functions in the python code", "do the
  same thing"
Chosen pole: (a)
Raw-type evaluator call sites:
  1. new StringTokenizer().tokenize("hello"): Token
  2. new NumericTokenizer().tokenize(42): Token
  3. new TemporalTokenizer().tokenize(LocalDate.now()): Token
  4. tokenizer.tokenizeBatch(List("a", "b").iterator).toList: List[Token]
  5. token.withMetadata(Map("source" -> "user")): Token
  6. TokenType.STRING: TokenType           // enum member by Python id
  7. (new TokenizerBuilder).build: BaseTokenizer   // no function wrapping
```

**What NOT to write (iter_2/iter_3 anti-patterns combined):**

```scala
// 1. Wrapper ADT forces caller to wrap raw String:
class StringTokenizer {
  def tokenize(value: StringLike): Token = ???          // WRONG
}

// 2. Return wrapped in Try — breaks `: Token` ascription:
class StringTokenizer2 {
  def tokenize(value: String): Try[Token] = ???         // WRONG
}

// 3. Function-returning builder — breaks `: BaseTokenizer`:
class TokenizerBuilder {
  def build: Any => Either[String, Token] = ???         // WRONG (iter_3)
}

// 4. (String, Any)* varargs cannot accept Map or named kwargs:
class Token {
  def withMetadata(pairs: (String, Any)*): Token = ???  // WRONG
}

// 5. Hand-rolled sealed trait where Python has Enum:
sealed trait TokenType
object TokenType {
  case object String extends TokenType { val value = "string" }  // WRONG
}

// 6. Enum member rename STRING → String (iter_3 added):
enum TokenType(val value: String):
  case String  extends TokenType("string")              // WRONG — identifier renamed
  case Numeric extends TokenType("numeric")             // WRONG
```

**What TO write:**

```scala
class StringTokenizer {
  def tokenize(value: String): Token      = ???   // overload
  def tokenize(value: Array[Byte]): Token = ???   // overload
  // Return type is Token, not Try[Token]. Throw on error as Python does.
}

class Token {
  def withMetadata(metadata: Map[String, Any]): Token = ???
}

class TokenizerBuilder {
  // Return a BaseTokenizer directly — not T => Either[E, Token]:
  def build: BaseTokenizer = ???
}

// Scala 2:
object TokenType extends Enumeration {
  val STRING, NUMERIC, TEMPORAL, STRUCTURED, BINARY, NULL = Value
}
// Scala 3:
enum TokenType(val value: String):
  case STRING     extends TokenType("string")   // identifier verbatim
  case NUMERIC    extends TokenType("numeric")
  case TEMPORAL   extends TokenType("temporal")
  // ...
```

And every class in the Python source (not just the 13 named in the
task) appears in `Output.scala` — see
`references/enumerate-python-symbols.md`.

---

## 5. Worked example — pole (b) (derived from iter_1 recurrence)

**Task statement (quoted):** "The translation should not be a word-to-
word translation. Write it as a proficient Scala developer would — use
proper abstractions for representing data, handle errors and exceptions
naturally in Scala, use immutable collections."

**Required artifact:**

```
Named public APIs (verbatim from the task):
  (none listed — task describes behavior, not API)
Signal phrase (verbatim quote from the task):
  "proficient Scala developer", "proper abstractions for representing
  data", "handle errors naturally in Scala"
Chosen pole: (b)
Raw-type evaluator call sites:
  (not applicable — no Python-shaped call sites given; evaluator judges
  idiomatic quality, not API shape)
```

**What NOT to write:**

```scala
// WRONG: Any + isinstance-style match on pole (b)
class BaseTokenizer[Any] {
  def tokenize(value: Any): Token = value match {
    case s: String => ???
    case _ => throw new IllegalArgumentException(...)
  }
}
```

**What TO write:** See
`references/scala-generics-for-python-typevars.md` §1 (bounded generics /
sealed ADT / type class / Scala-3 union) and §2 (`Try`/`Either`,
persistent builder, locale-safe formatting, `UpperCamelCase` enums).

---

## 6. Verification

Grep your emitted Scala for the pole-relevant anti-patterns.

**Pole (a)** — anti-patterns that break raw-type call sites:

```bash
# Hits are candidates for rewrite BEFORE submission on pole (a):
grep -nE ': Try\[|: Either\[|=> Either\[|=> Try\[|Iterator\[Try\[|\(String, Any\)\*|sealed trait.*TokenType|sealed trait.*(StrOrBytes|StringLike|TemporalValue|NumericValue)' Output.scala
```

Interpretation of hits:
- `: Try[T]`, `: Either[E, T]`, or `=> Either[E, T]` (function-returning)
  on a method return where Python returns raw `T` → rewrite to `: T` and
  throw on error; add parallel `methodTry` if desired. See
  `references/preserve-python-api.md` §6.
- `(String, Any)*` → rewrite to `Map[String, Any]` or a named-parameter
  case class. See §7.
- `sealed trait .*TokenType` (hand-rolled enum) → rewrite to
  `scala.Enumeration` or Scala-3 `enum`. See §8.
- `sealed trait .*(StrOrBytes|StringLike|TemporalValue|NumericValue|...)`
  wrapping Python union-typed inputs → rewrite the method to overloads or
  `Any`+match. See §1.

Also run the enum-member-name check (iter_3 regression):

```bash
# For every Python enum, extract member identifiers; confirm Scala has each verbatim.
python_members=$(grep -E '^    [A-Z_][A-Z_0-9]* = ' <python-file> | awk -F' *= *' '{print $1}' | awk '{$1=$1}1')
for m in $python_members; do
    grep -q "\\b$m\\b" Output.scala || echo "MISSING ENUM MEMBER: $m"
done
```

Each missing member is a §9 violation — rename the Scala identifier back
to the Python form (`String` → `STRING`, etc.) before submitting.

And the dropped-class scan (iter_3 regression):

```bash
# Every public class/function in the Python source must appear in Output.scala.
for sym in $(grep -oE '^(class|def) \w+' <python-file> | awk '{print $2}'); do
    grep -q "\\b$sym\\b" Output.scala || echo "MISSING: $sym"
done
```

Each miss is a dropped-class divergence — see
`references/enumerate-python-symbols.md`.

**Pole (b)** — anti-patterns the grader penalizes:

```bash
grep -nE '\bextends .+\[Any\]|throw new .*Exception|mutable\.(ListBuffer|Map|Set)|%\.[0-9]+f|case object [A-Z_]{2,}' Output.scala
```

Any hit is a candidate for rewrite. If every hit is intentional (justified
by a corresponding Python API-shape constraint and you are in `mixed`
mode), proceed; otherwise, fix the hit per the corresponding rule in
`references/scala-generics-for-python-typevars.md`.

If a hit survives even after rewrite attempts, re-read the task statement
one more time — the axis may actually be `mixed` or the opposite pole,
and the rewrite pressure was coming from a signal you did not count
during §3.

**Corrective step on failure:** if any pole-(a) hit survives on a pole-(a)
task, do NOT submit. Return to `references/preserve-python-api.md`
(§1 for ADT wrappers, §6 for return types and function wrapping, §7 for
`**kwargs`, §8 for enum structure, §9 for enum member names) and apply
the fix at the source. If any class is missing from the dropped-class
scan, see `references/enumerate-python-symbols.md` §5. Re-run the greps.
Repeat until clean.
