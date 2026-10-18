# Idiomatic Scala expressions of a Python TypeVar-constrained hierarchy

When the task statement signals pole (b) ("proficient Scala developer",
"idiomatic Scala", "use the Scala type system", "proper abstractions") and
the Python source encodes a type-parametric hierarchy via `TypeVar` with
distinct constraints per subclass, the Scala counterpart is **not**
`BaseFoo[Any]` + `isinstance`-style pattern match. That is the exact
"word-to-word" translation the grader penalizes.

Read this chapter whenever:
- The Python source has a `TypeVar(...)` with explicit constraints
  (`TypeVar("T", str, bytes)`) or a bound (`TypeVar("T", bound=Number)`),
  AND
- The task statement signals pole (b) (see
  `references/task-statement-axis-calibration.md`).

Skip when the task shows an evaluator call site with raw Python types or
otherwise signals pole (a) — in that case `Any` + pattern match is the
correct choice (see `references/preserve-python-api.md` §1).

---

## 1. The four Scala expressions, in preference order

Pick the first option whose shape matches the Python TypeVar:

### Option 1 — Bounded type parameter on the subclass

Use when each Python subclass pins the TypeVar to a single concrete type.

```scala
// Python:
//   T = TypeVar("T", str, bytes)
//   class StringTokenizer(BaseTokenizer[T]): ...
// Scala (one class per concrete arm):
abstract class BaseTokenizer[T] {
  def tokenize(value: T): Token
}
class StringTokenizerStr extends BaseTokenizer[String] {
  def tokenize(value: String): Token = ???
}
class StringTokenizerBytes extends BaseTokenizer[Array[Byte]] {
  def tokenize(value: Array[Byte]): Token = ???
}
```

### Option 2 — Sealed ADT as the type parameter

Use when the Python TypeVar has a closed set of acceptable arms AND you
want a single subclass that handles all of them with exhaustive matching.

```scala
sealed trait StrOrBytes
object StrOrBytes {
  case class Str(s: String)         extends StrOrBytes
  case class Bytes(b: Array[Byte])  extends StrOrBytes
}

class StringTokenizer extends BaseTokenizer[StrOrBytes] {
  def tokenize(value: StrOrBytes): Token = value match {
    case StrOrBytes.Str(s)   => ???
    case StrOrBytes.Bytes(b) => ???
    // compiler warns on non-exhaustive match
  }
}
```

### Option 3 — Type class constraint

Use when the Python TypeVar is numeric-bounded
(`T = TypeVar("T", int, float, Decimal)`) AND one tokenizer instance is
expected to operate on a single element type at a time.

```scala
class NumericTokenizer[T: Numeric] extends BaseTokenizer[T] {
  def tokenize(value: T): Token = {
    val n = implicitly[Numeric[T]].toDouble(value)
    ???
  }
}
// Usage: new NumericTokenizer[Int], new NumericTokenizer[BigDecimal], ...
```

### Option 4 — Scala 3 union type

Use when running on Scala 3 AND the Python source uses `A | B` and the
union is small (2–3 arms).

```scala
class TemporalTokenizer extends BaseTokenizer[LocalDateTime | LocalDate] {
  def tokenize(value: LocalDateTime | LocalDate): Token = value match {
    case dt: LocalDateTime => ???
    case d:  LocalDate     => ???
  }
}
```

### Decision rule

```
Python TypeVar shape                              Scala expression
--------------------------------------------      -----------------------------
TypeVar("T", str, bytes) — closed concrete arms   Option 1 (one class per arm)
                                                  OR Option 2 (sealed ADT)
TypeVar("T", int, float, Decimal) — numeric       Option 3 (type class [T: Numeric])
A | B union, Scala 3 available                    Option 4 (union type)
Any of the above, Scala 2.13 only                 Option 1 or Option 2
```

Never pick `BaseTokenizer[Any]` + `isinstance`-style match on pole-(b).

---

## 2. Companion idiomatic rules on pole-(b) translations

The generics shape alone does not satisfy a pole-(b) grader. Pair the
generics choice with these three companion rules — all three were missed
in the iter_1 failure.

### 2a. Error channel: `Try` / `Either`, not thrown exceptions

```scala
import scala.util.{Try, Success, Failure}

// Anti-pattern (pole-(a) default, wrong on pole-(b)):
def tokenize(value: Any): Token = value match {
  case s: String => ???
  case _ => throw new IllegalArgumentException(s"Unsupported: $value")
}

// Idiomatic pole-(b) form:
def tokenize(value: StrOrBytes): Try[Token] = value match {
  case StrOrBytes.Str(s)   => Try(/* ... */)
  case StrOrBytes.Bytes(b) => Try(/* ... */)
}

// Or Either[E, A] with a typed error:
sealed trait TokenizeError
case class UnsupportedType(got: String) extends TokenizeError

def tokenize(value: Any): Either[TokenizeError, Token] = value match {
  case s: String => Right(???)
  case other     => Left(UnsupportedType(other.getClass.getName))
}
```

### 2b. Public builder: persistent copy-based, not `mutable.ListBuffer` + `var`

```scala
// Anti-pattern:
class TokenizerBuilder {
  private val buf = scala.collection.mutable.ListBuffer.empty[Tokenizer]
  private var lowercase: Boolean = false
  def withLowercase(v: Boolean): TokenizerBuilder = { lowercase = v; this }
  def add(t: Tokenizer): TokenizerBuilder = { buf += t; this }
  def build(): CompositeTokenizer = new CompositeTokenizer(buf.toList, lowercase)
}

// Idiomatic form (persistent, copy-based):
case class TokenizerBuilder(
  tokenizers: List[Tokenizer] = Nil,
  lowercase:  Boolean         = false
) {
  def withLowercase(v: Boolean): TokenizerBuilder = copy(lowercase = v)
  def add(t: Tokenizer): TokenizerBuilder = copy(tokenizers = tokenizers :+ t)
  def build(): CompositeTokenizer = new CompositeTokenizer(tokenizers, lowercase)
}
// Each `with*` / `add` returns a NEW builder; the previous one is unchanged.
```

### 2c. Locale-safe numeric and date formatting

```scala
import java.util.Locale
import java.time.format.DateTimeFormatter

// Anti-pattern — default locale leaks (decimal comma on fr_FR, de_DE, …):
val s = "%.3f".format(x)   // uses JVM default locale
val d = DateTimeFormatter.ofPattern("MMM d, yyyy").format(dt)  // locale-sensitive

// Idiomatic form — pin to Locale.ROOT (or an explicit Locale):
val s = String.format(Locale.ROOT, "%.3f", java.lang.Double.valueOf(x))
val d = DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.ROOT).format(dt)
```

### Decision rule for enum member casing

```
Task statement contains "Scala naming conventions"           → UpperCamelCase
                       / "proficient Scala developer"
                       / "idiomatic Scala"

Task statement contains Python call site using the Python    → SCREAMING_CASE
form (`TokenType.STRING`, `Color.RED`) that the evaluator
will replicate verbatim

Neither of the above                                         → UpperCamelCase
                                                               (Scala default)
```

```scala
// Idiomatic pole-(b) form:
sealed trait TokenType
object TokenType {
  case object String     extends TokenType { val value = "string" }
  case object Numeric    extends TokenType { val value = "numeric" }
  case object Temporal   extends TokenType { val value = "temporal" }
  case object Structured extends TokenType { val value = "structured" }
  case object Binary     extends TokenType { val value = "binary" }
  case object Null       extends TokenType { val value = "null" }
}
```

---

## 3. Verification

Run this grep against your emitted Scala. Each hit is a candidate for
rewrite via the matching rule above.

```bash
# Pole-(b) anti-pattern scan
grep -nE 'extends .+\[Any\]|throw new .*Exception|mutable\.(ListBuffer|Map|Set|ArrayBuffer)|"%\.[0-9]+f"|case object [A-Z_]{2,} ' Output.scala
```

Interpretation of hits (what to do next on each):

- `extends .+\[Any\]` → consult §1, pick Option 1–4, rewrite the subclass
  signatures.
- `throw new .*Exception` at a public method → wrap the method body in
  `Try { ... }` or convert to `Either` per §2a.
- `mutable.*` inside a `*Builder` class → convert to a case class with
  `copy(...)` per §2b.
- `"%.Nf"` or default-locale `String.format` → add `Locale.ROOT` per §2c.
- `case object [A-Z_]{2,}` in an `enum`/sealed hierarchy → rename to
  `UpperCamelCase` unless the task shows a Python call site relying on the
  Python form (then it is a pole-(a) override, record the exception in your
  plan).

If any rewrite propagates to a public method signature named in the task
statement, re-run the pole-(a) verification in
`references/preserve-python-api.md` §End-to-end to confirm the raw-type
call sites still compile — you may have slipped from pole (b) into mixed
mode.
