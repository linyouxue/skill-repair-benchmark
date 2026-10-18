# Preserving the Python public API shape in Scala

The evaluator for a Python→Scala translation task compares the Scala API
against the Python API: it constructs objects, calls methods, and probes
fields using the **Python names**, the **Python-accepted argument types**,
and expects the **Python return types** back. **It also reads string
values out of maps, enum `.value` strings, and `__name__`-derived tags
using the Python spellings** — camelCased or JVM-renamed string literals
are drift the compile check will not catch. A Scala file that compiles
cleanly and passes its own hand-written tests can still score 0 if the
call sites the evaluator uses do not type-check, OR if the strings it
reads back out of your maps/enums do not match the Python spellings.
This chapter documents thirteen divergence classes and the corrective
rewrite for each.

Read this chapter whenever translating a Python module whose public symbols
are named in the task statement, especially when the Python API uses union
types (`A | B`), runtime type dispatch, `snake_case` keyword parameters,
`**kwargs`, raw (non-`Try`/`Optional`) return types, builder methods that
return a tokenizer/token directly, `Enum` subclasses, enum member
identifiers written in SCREAMING_CASE, **string literals used as metadata
keys or type tags**, **a single-entry-point `isinstance` dispatch**, or
when you are about to add "convenience" methods / `Option` dispatch
branches not present in the Python source.

---

## 1. Union-typed parameters (`A | B`): overload or `Any`+match, not wrapper ADT

Python signature:

```python
# accepts str or bytes directly
class StringTokenizer:
    def tokenize(self, value: str | bytes) -> Token: ...
```

**Anti-pattern — wrapper ADT forced on callers:**

```scala
sealed trait StringOrBytes
object StringOrBytes {
  case class Str(s: String) extends StringOrBytes
  case class Bytes(b: Array[Byte]) extends StringOrBytes
}

class StringTokenizer {
  def tokenize(value: StringOrBytes): Token = value match {
    case StringOrBytes.Str(s)   => ???
    case StringOrBytes.Bytes(b) => ???
  }
}
// Evaluator call `st.tokenize("abc")` does NOT type-check.
```

**Fix A — method overloads (preferred when the union has few concrete arms):**

```scala
class StringTokenizer {
  def tokenize(value: String): Token = ???
  def tokenize(value: Array[Byte]): Token = ???
}
// Both `st.tokenize("abc")` and `st.tokenize(bytes)` type-check verbatim.
```

**Fix B — `Any` parameter with internal pattern match (preferred when the
union is open-ended or has many arms, e.g. `int | float | Decimal`):**

```scala
class NumericTokenizer {
  def tokenize(value: Any): Token = value match {
    case i: Int        => ???
    case l: Long       => ???
    case d: Double     => ???
    case bd: BigDecimal => ???
    case other => throw new IllegalArgumentException(
      s"Unsupported numeric type: ${other.getClass}")
  }
}
// `nt.tokenize(3)`, `nt.tokenize(3.14)`, `nt.tokenize(BigDecimal("1.0"))` all work.
```

### Decision rule

- 2–3 concrete arms, all closed types → use overloads (Fix A).
- Open-ended / Python abstract base (`numbers.Number`, `datetime` hierarchy)
  → use `Any` + pattern match (Fix B).
- Never require the caller to wrap in a sealed ADT the Python caller did not
  write. The ADT name does not matter — `StringOrBytes`, `StrOrBytes`,
  `StringLike`, `NumericValue`, `TemporalValue` are all the same anti-
  pattern under different names.

### Verification

Write a one-line Scala snippet using **only raw Python-shaped types** and
confirm it compiles:

```scala
// Verification snippet — no imports of translator-defined helpers
val t1 = (new StringTokenizer).tokenize("abc")
val t2 = (new StringTokenizer).tokenize("hi".getBytes)
val t3 = (new NumericTokenizer).tokenize(3)
val t4 = (new NumericTokenizer).tokenize(3.14)
```

If any line fails to compile, go back and switch the parameter from a wrapper
ADT to an overload set or `Any`+match before continuing.

---

## 2. Runtime-dispatch classes stay as one class

Python signature:

```python
# ONE class that dispatches on runtime type of the argument
class NumericTokenizer:
    def __init__(self, format_options: dict | None = None):
        self.format_options = format_options or {}

    def tokenize(self, value):   # int | float | Decimal
        if isinstance(value, int):      ...
        elif isinstance(value, float):  ...
        elif isinstance(value, Decimal): ...
```

**Anti-pattern — parametric class forcing one instance per element type:**

```scala
class NumericTokenizer[A: Numeric](formatOptions: Map[String, String] = Map.empty) {
  def tokenize(value: A): Token = ???
}
// A single evaluator instance cannot tokenize `3` AND `3.14` AND `BigDecimal("1")`.
```

**Fix — one non-parametric class with runtime pattern match:**

```scala
class NumericTokenizer(val formatOptions: Map[String, String] = Map.empty) {
  def tokenize(value: Any): Token = value match {
    case i: Int         => ???
    case l: Long        => ???
    case d: Double      => ???
    case bd: BigDecimal => ???
    case other => throw new IllegalArgumentException(
      s"Unsupported numeric: ${other.getClass}")
  }
}
```

### Decision rule

If the Python class dispatches on `isinstance` (or on the runtime type via
`type(x)`) under **one class name**, the Scala counterpart is **one class**
too. Resist the pull to make it generic — that is an idiomatic-Scala reflex
that breaks evaluator usage.

### Verification

```scala
val nt = new NumericTokenizer()
val a = nt.tokenize(3)
val b = nt.tokenize(3.14)
val c = nt.tokenize(BigDecimal("1.0"))
```

If this does not compile from a single `nt` instance, revert the parametric
signature.

---

## 3. Constructor parameter names and types: preserve verbatim

Python signature:

```python
class TemporalTokenizer:
    def __init__(self, format_str: str | None = None):
        self.format_str = format_str
```

**Anti-pattern — simultaneously rename AND retype:**

```scala
class TemporalTokenizer(val format: Option[DateTimeFormatter] = None)
// Breaks both `TemporalTokenizer(format_str="%Y-%m-%d")` (name) AND
// construction via a format string (type).
```

**Fix — preserve the name verbatim, preserve the accepted type verbatim:**

```scala
class TemporalTokenizer(val format_str: Option[String] = None) {
  // Internal use of DateTimeFormatter is fine, derived lazily:
  private lazy val formatter: Option[DateTimeFormatter] =
    format_str.map(DateTimeFormatter.ofPattern)
}
// Alternative: camelCase + snake_case alias
class TemporalTokenizer(val formatStr: Option[String] = None) {
  // Scala allows named-arg call via either name only if both are declared;
  // when in doubt, keep the Python snake_case name on constructor params.
}
```

### Decision rule

Change at most **one** of {name, type} per constructor parameter, and change
neither when:
- the evaluator might call by keyword (`ClassName(format_str="...")`), OR
- the parameter name is referenced in the task statement, OR
- the parameter is a kwarg with a default.

For constructor keyword parameters, prefer keeping the Python `snake_case`
name verbatim; `camelCase` is a soft convention, not a correctness rule.

### Verification

```scala
val t1 = new TemporalTokenizer(format_str = Some("yyyy-MM-dd"))
val t2 = new TemporalTokenizer()  // default
```

If keyword construction fails, rename the parameter back.

---

## 4. Idiomatic field/method renames are opt-in, not default

Python signature:

```python
class Token:
    def __init__(self, token_type: TokenType, value: Any):
        self.token_type = token_type
        self.value = value

class Tokenizable:
    def to_token(self) -> Token: ...
```

**Anti-pattern — blanket `snake_case` → `camelCase`:**

```scala
case class Token(tokenType: TokenType, value: Any)
trait Tokenizable {
  def toToken: Token
}
// Reflective evaluator probes for `token_type` field or `to_token` method miss.
```

**Fix — define both names when in doubt:**

```scala
case class Token(token_type: TokenType, value: Any) {
  def tokenType: TokenType = token_type  // optional idiomatic alias
}

trait Tokenizable {
  def to_token: Token
  def toToken: Token = to_token  // optional idiomatic alias
}
```

### Decision rule

Rename `snake_case` → `camelCase` only when all three hold:
1. The field/method name is **not** referenced in the task statement.
2. The task does **not** mention reflection, serialization keys, or
   source-pattern probes.
3. No sibling evidence (nearby `enum` values, keyword constructor parameters)
   relies on the Python name.

When any of the three is unclear, keep the Python name verbatim or provide
both.

### Verification

Grep the task statement for every public symbol you renamed. Any hit on the
Python form is a signal to add the snake_case alias back.

---

## 5. No mid-task paradigm swaps

If an overload fails to resolve (e.g. erasure collision on
`def tokenize(s: Seq[String])` vs `def tokenize(s: Seq[Int])`), **fix the
overload locally** — rename one method, add a disambiguating implicit, or
split into two distinctly-named methods. Do **not** flip the surrounding
paradigm (e.g. change `Tokenizable[-A]` from a type class to a bare subtype
trait) to dodge the compile error, because that propagates to every
`extends`/`with` site and silently changes the API shape of unrelated
classes.

**Example — localized fix (preferred):**

```scala
trait Tokenizable[-A] {
  def toToken(a: A): Token
}
// If an overload collides on erasure, rename:
def tokenizeString(s: String): Token = ???
def tokenizeBytes(b: Array[Byte]): Token = ???
// NOT: delete the type class and replace with `trait Tokenizable { def toToken: Token }`.
```

### Decision rule

When a compile error pushes you toward a structural rewrite that touches
more than the one method producing the error, pause and ask: "Does this
rewrite change the public shape of any symbol the evaluator will probe?" If
yes, prefer a local disambiguation (method rename, explicit type ascription,
helper object) over the structural rewrite.

### Verification

Diff the final Scala against your planned signatures (step 2 of the
translation workflow). Any symbol whose declared `trait`/`class`/`extends`
clause changed between plan and emission is a candidate rollback.

---

## 6. Return types: preserve verbatim (no `Try` / `Either` / `Option` / function wrapping)

Python signatures:

```python
class BaseTokenizer:
    def tokenize(self, value) -> Token: ...                  # returns Token
    def tokenize_batch(self, values) -> Iterator[Token]: ... # returns Iterator[Token]

class TokenizerBuilder:
    def build(self) -> BaseTokenizer: ...                    # returns a tokenizer
```

**Anti-pattern 1 — wrapping Python-returns-raw in a monadic error channel:**

```scala
import scala.util.Try

abstract class BaseTokenizer {
  def tokenize(value: Any): Try[Token] = ???                        // WRONG
  def tokenizeBatch(values: Iterator[Any]): Iterator[Try[Token]]    // WRONG
    = ???
}

// Every evaluator call site must now unwrap:
tokenizer.tokenize("abc").get           // forced `.get` or match
tokenizer.tokenizeBatch(xs).map(_.get)  // forced map+get
```

**Anti-pattern 2 — returning a function in place of a raw value (iter_3):**

```scala
class TokenizerBuilder {
  // Python `build(self) -> BaseTokenizer`, Scala returns a FUNCTION:
  def build: Any => Either[String, Token] = (value: Any) => ???     // WRONG
}

// Evaluator wanted `builder.build.tokenize("hi"): Token`.
// What they get is `builder.build("hi"): Either[String, Token]` — different
// identifier shape, different return type, both wrong.
```

Every one of the following is a return-type divergence on pole (a):

- `: Try[T]` where Python returns `T`
- `: Either[E, T]` where Python returns `T`
- `: Option[T]` where Python returns raw `T` (not `Optional[T]`)
- `: T => R` or `: T => Either[E, R]` in place of `R` — function-returning
  is wrapping too; a Python method that returns a tokenizer must not become
  a Scala method that returns `(input => Either[E, Token])`.

**Fix — return the raw Python return type; throw on error as Python does:**

```scala
abstract class BaseTokenizer {
  def tokenize(value: Any): Token = ???                      // return Token
  def tokenizeBatch(values: Iterator[Any]): Iterator[Token]  // return Iterator[Token]
    = values.map(tokenize)
  // On error, throw IllegalArgumentException / similar — Python does.
}

class TokenizerBuilder {
  def build: BaseTokenizer = ???                             // return the tokenizer
}

// Evaluator call sites read naturally:
val t  = tokenizer.tokenize("abc"): Token
val ts = tokenizer.tokenizeBatch(xs).toList: List[Token]
val tk = (new TokenizerBuilder).build.tokenize("hi"): Token
```

**Fix (optional, if error-channel idiomaticity is explicitly desired) —
offer a PARALLEL method, leave the primary method untouched:**

```scala
abstract class BaseTokenizer {
  def tokenize(value: Any): Token = ???                      // primary, unchanged
  def tokenizeTry(value: Any): Try[Token] = Try(tokenize(value))        // parallel
  def tokenizeEither(value: Any): Either[Throwable, Token] =            // parallel
    Try(tokenize(value)).toEither
}
```

### Decision rule

If the Python signature is `def method(...) -> T` (no `Optional`, no
`Union[T, Exception]`-equivalent), the Scala signature is
`def method(...): T` on pole (a). Wrap the body in `try` internally if you
must, but do **not** leak `Try[T]` / `Either[E, T]` / `Option[T]` /
`T => R` into the public return. The evaluator compares the return site,
not the error semantics.

Exceptions: if Python returns `Optional[T]` / `T | None`, Scala returns
`Option[T]`; those are the same shape under translation.

### Verification

Grep for return-type wrapping on public methods:

```bash
grep -nE 'def [a-zA-Z_][a-zA-Z0-9_]*\([^)]*\): (Try|Either|Option)\[|=> (Try|Either)\[' Output.scala
```

Each hit on a method whose Python counterpart returns a raw type is a
rewrite candidate. Corrective action: unwrap the return to the raw type,
move error handling into a throw inside the method body, and if error-
channel idiomaticity is important, add a parallel `methodTry` /
`methodEither` beside it. The `=> (Try|Either)` arm catches the
function-wrapping anti-pattern (`build: T => Either[E, R]`).

---

## 7. `**kwargs` → `Map[String, Any]` or named-parameter case class, not varargs

Python signature:

```python
class Token:
    def with_metadata(self, **kwargs) -> "Token":
        return Token(..., metadata={**self.metadata, **kwargs})
```

**Anti-pattern — `(String, Any)*` varargs:**

```scala
case class Token(metadata: Map[String, Any] = Map.empty) {
  def withMetadata(pairs: (String, Any)*): Token =    // WRONG
    copy(metadata = metadata ++ pairs.toMap)
}

// Evaluator writing Python-call-site style CANNOT call this:
token.withMetadata(source = "user", confidence = 0.9)   // compile error
// They would have to write:
token.withMetadata("source" -> "user", "confidence" -> 0.9)
// which no Python-shaped evaluator script writes.
```

**Fix A — accept a `Map[String, Any]` (closest to Python `**kwargs`):**

```scala
case class Token(metadata: Map[String, Any] = Map.empty) {
  def withMetadata(metadata: Map[String, Any]): Token =
    copy(metadata = this.metadata ++ metadata)
}
// Evaluator: token.withMetadata(Map("source" -> "user"))
```

**Fix B — named-parameter case class (when the kwarg set is closed and
known from the Python source):**

```scala
case class Metadata(
  source:     Option[String] = None,
  confidence: Option[Double] = None,
  // ...one field per known kwarg from the Python source
)

case class Token(metadata: Metadata = Metadata()) {
  def withMetadata(m: Metadata): Token = copy(metadata = m)
}
// Evaluator: token.withMetadata(Metadata(source = Some("user"),
//                                        confidence = Some(0.9)))
```

### Decision rule

- Python `**kwargs` with an **open** key set (the Python code reads keys
  dynamically or treats `kwargs` as a free-form map) → **Fix A**
  (`Map[String, Any]`).
- Python `**kwargs` with a **closed** key set (the Python code reads only
  a known list of keys like `kwargs.get("source")`, `kwargs.get("confidence")`)
  → **Fix B** (named-parameter case class) is more idiomatic, but **Fix A**
  is always safe.
- Never use `(String, Any)*` varargs — the call-site shape (tuple
  literals) does not match any Python-style evaluator script.

### Verification

Grep for `(String, Any)*` and similar vararg shapes on public methods:

```bash
grep -nE 'def [a-zA-Z_][a-zA-Z0-9_]*\([^)]*(String|Any), [^)]*\*\)' Output.scala
```

Corrective action on hit: convert to `Map[String, Any]` or a
named-parameter case class per the decision rule.

---

## 8. Python `Enum` structure → `scala.Enumeration` / Scala-3 `enum`, not hand-rolled sealed trait

Python signature:

```python
from enum import Enum

class TokenType(Enum):
    STRING     = "string"
    NUMERIC    = "numeric"
    TEMPORAL   = "temporal"
    STRUCTURED = "structured"
    BINARY     = "binary"
    NULL       = "null"
```

Python callers can:
- construct from a string via `TokenType("string")`;
- probe `.value` (the string) and `.name` (the member name);
- iterate via `list(TokenType)`;
- pattern-match on members.

**Anti-pattern — hand-rolled sealed-trait hierarchy:**

```scala
sealed trait TokenType { def value: String }
object TokenType {
  case object String     extends TokenType { val value = "string" }
  case object Numeric    extends TokenType { val value = "numeric" }
  case object Temporal   extends TokenType { val value = "temporal" }
  case object Structured extends TokenType { val value = "structured" }
  case object Binary     extends TokenType { val value = "binary" }
  case object Null       extends TokenType { val value = "null" }
}
// Shape mismatches: no `.name`, no built-in iteration, no `.values`,
// no `TokenType.withName("string")`. Pattern match works but shape probes fail.
// Also: member names were renamed from SCREAMING_CASE — see §9 below.
```

**Fix A — `scala.Enumeration` (Scala 2) with member names preserved verbatim:**

```scala
object TokenType extends Enumeration {
  // Pole (a): member identifiers stay SCREAMING_CASE — see §9
  val STRING, NUMERIC, TEMPORAL, STRUCTURED, BINARY, NULL = Value
  // Access: TokenType.STRING, TokenType.values, TokenType.withName("STRING")
}
// If the Python `.value` is a lowercase string distinct from the member
// name, override:
object TokenType extends Enumeration {
  type TokenType = Value
  val STRING     = Value("string")
  val NUMERIC    = Value("numeric")
  val TEMPORAL   = Value("temporal")
  val STRUCTURED = Value("structured")
  val BINARY     = Value("binary")
  val NULL       = Value("null")
  // TokenType.STRING.toString == "string"; TokenType.withName("string") works.
}
```

**Fix B — Scala-3 `enum` (when the project is Scala 3), member names verbatim:**

```scala
enum TokenType(val value: String):
  // Pole (a): member identifiers stay SCREAMING_CASE — see §9
  case STRING     extends TokenType("string")
  case NUMERIC    extends TokenType("numeric")
  case TEMPORAL   extends TokenType("temporal")
  case STRUCTURED extends TokenType("structured")
  case BINARY     extends TokenType("binary")
  case NULL       extends TokenType("null")

// Access: TokenType.STRING, TokenType.values, TokenType.valueOf("STRING")
```

### Decision rule

- The task's Python source has `class X(Enum)` or `class X(IntEnum)` AND
  the task signals pole (a) → use `scala.Enumeration` (Scala 2) or
  Scala-3 `enum` (Scala 3), **and keep member names verbatim** (see §9).
- A hand-rolled `sealed trait X + case object` hierarchy is appropriate
  only when the Python shape is **not** an `Enum` (e.g. an ADT of
  structurally distinct cases) OR when the task explicitly signals
  pole (b) and no evaluator probe of `.name` / `.values` /
  `withName(...)` is expected.
- When uncertain on pole (a), prefer `Enumeration`/`enum`.

### Verification

Grep for hand-rolled enum shapes:

```bash
grep -nE 'sealed (trait|abstract class) [A-Z][a-zA-Z]*' Output.scala
```

For each hit, check whether the corresponding Python symbol is an `Enum`
subclass. If yes and pole is (a), rewrite to `Enumeration`/`enum`.

---

## 9. Enum member names verbatim — identifiers are public API, not formatting

**This rule recurred in iter_3 AND iter_4 verbatim on the same task
family despite being present in L2.** The identifier `TokenType.STRING`
is the symbol callers write; it is public API. The `UpperCamelCase`
Scala convention is a formatting preference that applies to pole (b)
only. On pole (a), copy the Python identifier character-for-character.
Scala accepts SCREAMING_CASE identifiers; there is no language-level
obstruction.

Python signature:

```python
class TokenType(Enum):
    STRING   = "string"
    NUMERIC  = "numeric"
    TEMPORAL = "temporal"
```

Evaluator call sites written in Python-call-site style:

```scala
val t: TokenType = TokenType.STRING             // identifier
val n: TokenType = TokenType.NUMERIC
val ts: Array[TokenType] = TokenType.values     // iteration
```

**Anti-pattern (iter_3, iter_4 recurrence) — rename to Scala `UpperCamelCase`:**

```scala
enum TokenType(val value: String):
  case String   extends TokenType("string")   // WRONG — identifier renamed
  case Numeric  extends TokenType("numeric")  // WRONG
  case Temporal extends TokenType("temporal") // WRONG

// Evaluator writing `TokenType.STRING` does NOT resolve.
// The underlying `.value` is still "string", but the identifier is gone.
```

The iter_3 and iter_4 agents justified this rename as "un-Scala to keep
SCREAMING_CASE". That justification applies to pole (b) only.

**Fix — preserve member names verbatim:**

```scala
// Scala 3:
enum TokenType(val value: String):
  case STRING   extends TokenType("string")
  case NUMERIC  extends TokenType("numeric")
  case TEMPORAL extends TokenType("temporal")

// Scala 2:
object TokenType extends Enumeration {
  val STRING   = Value("string")
  val NUMERIC  = Value("numeric")
  val TEMPORAL = Value("temporal")
}
```

### Decision rule

```
Python enum member identifier  | Pole (a) Scala identifier | Pole (b) Scala identifier
-------------------------------|---------------------------|--------------------------
STRING                         | STRING   (verbatim)       | String   (idiomatic)
Numeric                        | Numeric  (verbatim)       | Numeric  (coincides)
mixed_case                     | mixed_case (verbatim)     | mixedCase or MixedCase
```

The Python identifier IS the signal — no additional task-statement
evaluator snippet is required to trigger the pole-(a) rule. If the
Python source writes `STRING`, the Scala counterpart writes `STRING`.

### Verification

Grep for enum member identifiers that look renamed:

```bash
# For every Python enum, extract its member identifiers and confirm the
# Scala file contains each one verbatim:
python_members=$(grep -E '^    [A-Z_][A-Z_0-9]* = ' <python-file> | awk -F' *= *' '{print $1}' | awk '{$1=$1}1')
for m in $python_members; do
    grep -q "\\b$m\\b" Output.scala || echo "MISSING ENUM MEMBER: $m"
done
```

### Corrective step on failure

For each missing member name, open the enum definition in `Output.scala`:

1. Rename the Scala identifier back to the Python identifier verbatim
   (`String` → `STRING`, `Numeric` → `NUMERIC`, etc.).
2. If the identifier was being used elsewhere in your Scala (`case
   TokenType.String => ...`), update those references too.
3. Re-run the grep. Repeat until clean.
4. Do **not** submit on pole (a) while any Python member identifier is
   missing from the Scala source.

**If you are tempted to write `TokenType.String` instead of
`TokenType.STRING`: STOP. Re-read this section. The identifier is
public API — not formatting.**

---

## 10. String-literal values verbatim — the identifier/literal boundary

**This is iter_4's NEW dominant failure mode.** The agent correctly
renamed the *method name* `with_metadata` → `withMetadata` (consistent
with the task's named-API list showing camelCase method names) but then
extended camelCase into the **dict string literals** inside the method
body: `metadata("originalType")` where Python stores
`metadata["original_type"]`. The agent conflated the identifier rename
with a blanket "camelCase every snake_case thing".

**The rule — identifier renames stop at the identifier boundary.**

- An **identifier** is a name defined/declared in the Scala source: a
  class, method, field, parameter, enum member. Identifier renames
  (`with_metadata` → `withMetadata`) are allowed when the task names
  the Scala identifier in camelCase.
- A **string literal** is a value stored at runtime: a dict key, a type
  tag, an enum `.value`, an error message prefix. String literals are
  observable output; they must copy the Python source character-for-
  character.

Python source:

```python
class Token:
    def with_metadata(self, **kwargs) -> "Token": ...

class NumericTokenizer:
    def tokenize(self, value):
        metadata = {
            "original_type": type(value).__name__,   # string key, string value
            "token_type":    "numeric",              # string key, string value
        }
        return Token(..., metadata=metadata)
```

**Anti-pattern (iter_4) — camelCase extended past the identifier boundary:**

```scala
class Token {
  def withMetadata(m: Map[String, Any]): Token = ???     // identifier rename — OK
}

class NumericTokenizer {
  def tokenize(value: Int): Token = Token().withMetadata(Map(
    "originalType" -> value.getClass.getSimpleName,      // ❌ key camelCased;
                                                         // ❌ value is JVM name
    "tokenType"    -> "numeric",                         // ❌ key camelCased
  ))
}
// Grader reads token.metadata["original_type"] and sees None.
```

**Fix — identifier renames stop at the opening quote:**

```scala
class Token {
  def withMetadata(m: Map[String, Any]): Token = ???     // identifier — camelCase OK
}

class NumericTokenizer {
  def tokenize(value: Int): Token = Token().withMetadata(Map(
    "original_type" -> pythonTypeName(value),            // ✅ key snake_case;
                                                         //    value from §10b table
    "token_type"    -> "numeric",                        // ✅ key snake_case
  ))
}
```

### Decision rule — camelCase these; copy-verbatim these

| Thing | Form on pole (a) | Example |
|---|---|---|
| Scala class name | PascalCase | `class NumericTokenizer` |
| Scala method name | camelCase (if task names it so) or snake_case | `def withMetadata` |
| Scala field/val name | camelCase (if task names it so) or snake_case | `val formatStr` |
| Scala parameter name | camelCase (if task names it so) or snake_case | `(value: Int)` |
| **String literal used as a dict key** | **copy Python source verbatim** | `"original_type"` |
| **String literal used as a type tag** | **copy Python `type(x).__name__`** | `"int"`, `"str"`, `"float"` |
| **String literal used as enum `.value`** | **copy Python `.value` verbatim** | `"string"`, `"numeric"` |
| **Error-message prefix** | **copy Python source verbatim** | `"Unsupported numeric: "` |
| **Format pattern** | **copy Python verbatim** | `"%.3f"`, `"%Y-%m-%d"` |

If a string literal in your Scala method body does NOT exist in the
Python source character-for-character, it is a drift candidate. Re-read
the Python line that produces it and copy.

### 10b. Python-type-name mapping (`type(x).__name__`)

When Python stores `type(value).__name__`, the stored *value* is the
Python lowercase type name. The JVM equivalent
(`value.getClass.getSimpleName`) returns the capitalised Scala/Java form
and is **wrong** on pole (a).

| Python expression | Python output | Naive Scala (WRONG) | Correct Scala |
|---|---|---|---|
| `type(1).__name__` | `"int"` | `1.getClass.getSimpleName` → `"Integer"` | `"int"` |
| `type(1.5).__name__` | `"float"` | → `"Double"` | `"float"` |
| `type("s").__name__` | `"str"` | → `"String"` | `"str"` |
| `type(b"b").__name__` | `"bytes"` | → `"byte[]"` | `"bytes"` |
| `type(True).__name__` | `"bool"` | → `"Boolean"` | `"bool"` |
| `type([]).__name__` | `"list"` | → `"ArrayList"` | `"list"` |
| `type({}).__name__` | `"dict"` | → `"HashMap"` | `"dict"` |
| `type(()).__name__` | `"tuple"` | → `"Tuple2"` | `"tuple"` |
| `type(None).__name__` | `"NoneType"` | → `"null"` or NPE | `"NoneType"` |

**Helper — use this instead of `.getClass.getSimpleName` on pole (a):**

```scala
object PythonTypeName {
  def pythonTypeName(value: Any): String = value match {
    case null              => "NoneType"
    case _: Boolean        => "bool"       // check BEFORE Int — boxed Boolean
                                           // is an Integer on the JVM
    case _: Byte | _: Short | _: Int | _: Long   => "int"
    case _: Float | _: Double                    => "float"
    case _: Char | _: String                     => "str"
    case _: Array[Byte]                          => "bytes"
    case _: Map[_, _]                            => "dict"
    case _: scala.collection.Seq[_] | _: java.util.List[_] => "list"
    case _: Product                              => "tuple"
    case other => other.getClass.getSimpleName.toLowerCase
  }
}
```

See `references/execute-python-for-ground-truth.md` for the companion
"record Python outputs before writing Scala assertions" procedure that
catches string-literal drift at verification time.

### Verification

Grep for the Python type-name anti-pattern and camelCased metadata keys:

```bash
# Any .getClass.getSimpleName inside a method body that writes metadata
# is a §10b violation on pole (a):
grep -nE '\.getClass\.getSimpleName' Output.scala

# Any camelCased string literal that resembles a snake_case Python key:
grep -nE '"[a-z]+[A-Z][a-zA-Z]*"' Output.scala
```

### Corrective step on failure

- `.getClass.getSimpleName` hit → replace with `pythonTypeName(x)` from
  the helper above. Re-run the smoke test asserted against recorded
  Python output.
- camelCased string-literal hit → open the Python source line that stores
  the same key, copy the Python spelling (`"original_type"`,
  `"token_type"`, etc.) into the Scala literal verbatim. Scan for the
  same key elsewhere in `Output.scala` and update every occurrence.
- If no `# python recorded:` block exists in the plan, go to
  `references/execute-python-for-ground-truth.md` §1 and run the Python
  module BEFORE continuing. The agent that writes string literals from
  recall rather than recording is the agent that camelCases them.

---

## 11. Dispatch shape preserved — one Python entry point stays one Scala entry point

**This is iter_4's NEW shape divergence.** Python's `StringTokenizer`
has one class with one primary method `tokenize(self, value)` that
dispatches `str | bytes` through `isinstance` checks internally. The
iter_4 agent wrote `class StringTokenizer extends BaseTokenizer[String]`
with the `bytes` branch demoted to a separate overload. Same class name,
same method name, same return type — but the shape (one class, one
primary entry; one class, two entries) differs. Graders that iterate the
class's methods or probe for a single `tokenize` method handling the
union see the divergence.

Python source:

```python
class StringTokenizer(BaseTokenizer):
    def tokenize(self, value):     # ONE method, dispatches str|bytes internally
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return Token(value=value, ...)
```

**Anti-pattern (iter_4) — type-parametrize the parent, demote one branch to overload:**

```scala
abstract class BaseTokenizer[T] {
  def tokenize(value: T): Token
}

class StringTokenizer extends BaseTokenizer[String] {   // ❌ "primary" is String only
  def tokenize(value: String): Token = ???
  // bytes branch is a non-primary overload:
  def tokenize(value: Array[Byte]): Token = tokenize(new String(value, "UTF-8"))
}
// Shape mismatch: Python has one entry point for `str|bytes`; Scala has
// a type-parametrized primary that handles only one of the two.
```

**Fix A — one non-parametric class, overloads of the same name (both primary):**

```scala
abstract class BaseTokenizer {    // no type parameter
  def tokenize(value: Any): Token  // single abstract entry
}

class StringTokenizer extends BaseTokenizer {
  def tokenize(value: Any): Token = value match {
    case s: String      => ???
    case b: Array[Byte] => tokenize(new String(b, "UTF-8"))
    case other          => throw new IllegalArgumentException(s"Unsupported: $other")
  }
  // Optional co-primary overloads sharing a common dispatch path:
  def tokenize(value: String): Token      = tokenize(value: Any)
  def tokenize(value: Array[Byte]): Token = tokenize(value: Any)
}
```

**Fix B — if the Python base class has a type parameter, keep the
parametrization but ensure the shape-level dispatch matches:**

```scala
// Only when Python's BaseTokenizer itself is generic (e.g.
// `class BaseTokenizer(Generic[T])`); otherwise prefer Fix A.
```

### Decision rule

- Python class with **one** `tokenize` method dispatching `A | B` through
  `isinstance` → Scala class with **one** entry point (`Any`+match)
  OR co-equal overloads sharing a common private helper. Both overloads
  must be reachable from a single `tokenize` name.
- `extends BaseTokenizer[A]` demoting the `B` branch to a separate
  overload is a shape change: `BaseTokenizer[A]#tokenize` only accepts
  `A`, and the `B` overload lives on the subclass without being part of
  the base-class interface.
- If the Python base is itself generic (`class BaseTokenizer(Generic[T])`
  with `T` constrained per subclass), the Scala counterpart may be
  parametric — that is pole (b) and is governed by
  `references/scala-generics-for-python-typevars.md`. On pole (a), prefer
  Fix A.

### Verification

Grep for `extends .+\[.+\]` on subclasses of a Scala base whose Python
counterpart has no `Generic[T]`:

```bash
grep -nE 'class [A-Z]\w+ extends [A-Z]\w+\[[A-Z]\w+\]' Output.scala
```

Each hit is a candidate rewrite. Cross-check against the Python source:
does the Python base class have `Generic[T]` or inherit from a type
parameter? If no, the Scala should not type-parametrize the parent.

### Corrective step on failure

For each hit, rewrite as Fix A: remove the type parameter from the base,
widen the subclass `tokenize` to `Any`+match, and fold the demoted
overload back into the match arm.

---

## 12. No public-API additions — the public symbol set equals Python's, counted exactly

**This is iter_4's NEW "convenience" divergence.** The agent declared
`WhitespaceTokenizer` as a `case class` with extra convenience methods
(`tokenizeToStrings`, `tokenizeWithPositions`, `countTokens`) and extra
metadata keys (`"position"`, `"original"`) not in the Python source. The
agent justified them as "idiomatic Scala features". On pole (a), the
public API is **exactly** the Python surface — not a superset.

Python source (hypothetical, matching the iter_4 Python):

```python
class WhitespaceTokenizer(BaseTokenizer):
    def tokenize(self, value: str) -> Token:
        return Token(value=value.split(), ...)
```

**Anti-pattern (iter_4) — add convenience methods and metadata keys:**

```scala
case class WhitespaceTokenizer(???) extends BaseTokenizer {
  def tokenize(value: String): Token = Token(
    value = value.split("\\s+").toList,
    metadata = Map(
      "position" -> 0,              // ❌ no counterpart in Python source
      "original" -> value,          // ❌ no counterpart in Python source
    )
  )
  // ❌ Three convenience methods not in Python source:
  def tokenizeToStrings(v: String): List[String]       = ???
  def tokenizeWithPositions(v: String): List[(Int, String)] = ???
  def countTokens(v: String): Int                     = ???
}
```

**Fix — public symbol set equals the Python public symbol set:**

```scala
class WhitespaceTokenizer extends BaseTokenizer {
  def tokenize(value: String): Token = Token(
    value = value.split("\\s+").toList
    // Only metadata keys present in the Python source. If Python stores
    // none, Scala stores none.
  )
}
```

### Decision rule

Before adding a method, metadata key, parameter, or helper to your Scala
file, grep the Python source for its exact name/key spelling. If the
grep returns zero hits, you are adding to the public API — do not add
on pole (a).

Allowed additions on pole (a):
- `private` helpers used only within one method body.
- `private` lazy vals / internal data structures.
- `override` of methods inherited from the Python base class (shape is
  already defined by the base).

Not allowed on pole (a):
- `public` convenience methods not in the Python source
  (`tokenizeToStrings`, `countTokens`, `tokenizeWithPositions`, …).
- Extra metadata keys written to `Token.metadata` beyond what Python
  writes (`"position"`, `"original"`, `"source"` when Python stores
  only `"original_type"` and `"token_type"`).
- Extra constructor parameters not in the Python `__init__` signature.
- A `case class` for a class Python declared as a regular class
  (adds `copy`, `apply`, `unapply`, `productArity`, `productElement`,
  `equals`, `hashCode` to the public surface — see decision rule in §8
  for enum shape).

### Verification

For every public method defined on a Scala class, confirm the method
name exists in the Python source class with the same name:

```bash
# For each Scala public method in Output.scala:
grep -nE '^\s*def [a-z]\w+' Output.scala | while read line; do
    method=$(echo "$line" | awk '{print $2}' | sed 's/[(:].*//')
    grep -q "def ${method}\|def $(echo ${method} | sed -r 's/([A-Z])/_\L\1/g')" <python-file> \
        || echo "ADDED-ON-SCALA-SIDE: $method ($line)"
done
```

For every string literal used as a metadata key in Scala, confirm the
same literal (or its snake_case equivalent) is written in Python:

```bash
grep -oE '"[a-z_]+" ->' Output.scala | sort -u | while read key; do
    k=$(echo "$key" | tr -d '" ->')
    grep -q "\"$k\"\\|'$k'" <python-file> || echo "ADDED METADATA KEY: $k"
done
```

### Corrective step on failure

Each `ADDED-ON-SCALA-SIDE` or `ADDED METADATA KEY` hit is a public-API
addition. Delete the method/key from `Output.scala` before submitting on
pole (a). If a method's logic is genuinely useful internally, make it
`private`.

---

## 13. No code paths for Scala-only types (`Option`/`Try`/`Either`/`Future`)

**This is iter_4's NEW extra-code-path divergence.** The agent wrote
`UniversalTokenizer` with a match arm `case Some(v) => tokenize(v)` that
unwraps an `Option`. Python has no `Option` concept — every match arm
for a Scala-only type is an added code path that cannot possibly
correspond to Python semantics.

Python source:

```python
class UniversalTokenizer:
    def tokenize(self, value):
        if isinstance(value, str):
            return StringTokenizer().tokenize(value)
        if isinstance(value, int):
            return NumericTokenizer().tokenize(value)
        # ...no handling for Option / Try / Either / Future — these do not exist in Python
```

**Anti-pattern (iter_4) — unwrap a Scala-only type:**

```scala
class UniversalTokenizer {
  def tokenize(value: Any): Token = value match {
    case s: String  => new StringTokenizer().tokenize(s)
    case i: Int     => new NumericTokenizer().tokenize(i)
    case Some(v)    => tokenize(v)                     // ❌ Python has no Option
    case Success(v) => tokenize(v)                     // ❌ Python has no Try
    case Right(v)   => tokenize(v)                     // ❌ Python has no Either
    case _          => throw new IllegalArgumentException(...)
  }
}
```

**Fix — dispatch only on types the Python source dispatches on:**

```scala
class UniversalTokenizer {
  def tokenize(value: Any): Token = value match {
    case s: String  => new StringTokenizer().tokenize(s)
    case i: Int     => new NumericTokenizer().tokenize(i)
    // ... every arm corresponds to a Python isinstance check in the source
    case _ => throw new IllegalArgumentException(s"Unsupported: $value")
  }
}
```

### Decision rule

On pole (a), the arms of a dispatch `match` are exactly the Python
`isinstance` checks (or `type(x) ==` checks) in the Python source. If
Python has no `isinstance(x, Option)` check (and Python has no `Option`
to check against), Scala has no `case Some(_) =>` arm. The same holds
for `Try`, `Either`, `Future`, `Promise`, `IO`, `Resource`.

Exception: if the Scala method's **parameter type** is `Option[T]`
because Python's parameter type is `Optional[T]`, `case Some(_) =>` is
not an addition — it is destructuring a value that Python itself
produces as `Optional[T]`. The rule bans `Some` arms on `Any`-typed
dispatch methods whose Python counterpart has no `Optional` parameter.

### Verification

```bash
# Match arms on Scala-only types inside a dispatch method whose Python
# counterpart dispatches on Python types only:
grep -nE 'case (Some|None|Success|Failure|Right|Left)\b' Output.scala
```

Each hit is a candidate for removal — unless the enclosing method has an
`Option[T]` / `Try[T]` / `Either[E, T]` parameter whose Python
counterpart has the same shape.

### Corrective step on failure

For each hit on a public dispatch method whose Python counterpart has no
`Option`/`Try`/`Either` parameter, delete the arm. The default case
(`throw IllegalArgumentException`) absorbs the previously-matched
Scala-only type naturally — Python would raise `TypeError` on the same
input.

---

## End-to-end verification (run before finishing a translation)

1. **Signature diff.** For every public Python symbol named in the task
   statement AND every public symbol enumerated from the Python source
   (see `references/enumerate-python-symbols.md`), write a one-line
   comparison of its Python signature and its Scala signature. Flag any
   that differ on {name, param names, accepted argument types, **return
   type (including no function wrapping)**, kwargs shape, enum shape,
   **enum member identifiers**, **dispatch shape (one entry vs two
   entries)**}.
2. **Raw-type call-site snippet.** Compile a Scala snippet derived from
   the task statement's listed APIs AND exercising at least one API per
   class in the Python source (not from your own smoke test). It uses
   only Python-shaped raw types — no wrapper ADTs, no `.get` on `Try`,
   no `.right.get` on `Either`, no translator-defined helper imports.
   At least one line references an enum member by its Python identifier
   (`TokenType.STRING: TokenType`), so renamed members are caught.
3. **Python-output recording.** Run the Python module on 3–5
   representative inputs and record the exact outputs (metadata dict
   repr, enum `.name` and `.value`, `type(x).__name__` strings). See
   `references/execute-python-for-ground-truth.md`. Every assertion in
   your smoke test must quote a value from the recording — not a value
   you invented while writing Scala.
4. **Public-symbol-set equality.** Grep each Python public symbol name
   against `Output.scala`; every symbol must appear (dropped-class
   scan, §12 Verification). Grep each Scala public method name against
   the Python source; every method must correspond to a Python method
   (added-API scan, §12). Grep each Scala metadata key literal against
   the Python source; every key must appear in Python
   (string-literal scan, §10).
5. **EOF confirmation.** Confirm the last line of the Python source was
   read (not a tool clip at ~N lines). Any public symbol in the task
   statement that was not seen in the source is a signal to go back and
   read more before writing further Scala.

If any step fails: do not submit. Return to the specific section above
whose rule was violated (§1 ADTs, §6 return types including function
wrapping, §7 kwargs, §8 enum structure, §9 enum member names, §10
string literals + Python-type names, §11 dispatch shape, §12 public-API
additions, §13 Scala-only type arms) and apply the fix before re-running
the five checks.
