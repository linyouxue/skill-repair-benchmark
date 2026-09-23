---
name: python-scala-translation-playbook
version: 0.1.0
description: End-to-end playbook + template for translating a real Python module into compiling, idiomatic Scala 2.13.
---

# Python → Scala 2.13 Translation Playbook (module-level)

This skill is a **procedural checklist** for translating a real Python module into **compiling Scala 2.13** while preserving behavior and improving maintainability.

It is designed for tasks that require you to produce a single Scala file that mirrors a Python module’s public API (classes/functions) and runtime semantics, without doing a word-for-word translation.

## Constraints to respect

- **Scala 2.13** (avoid Scala 3-only features like `enum`, `given`, `extension`, opaque types).
- Prefer **standard library / JDK** (`java.time`, `java.util.regex`, etc.).
- Model Python absence & errors using **`Option` / `Either` / `Try`**.
- Keep hot paths efficient: avoid recompiling regex, avoid unnecessary intermediate collections.

---

## 0) First pass: inventory the Python module

Read the Python file and extract:

1. **Public surface** (must exist in Scala):
   - top-level functions
   - classes and their methods
   - constants / enums

2. **Data model**:
   - what “records” look like (strings, numbers, timestamps, maps)
   - what a “token” contains (type, value, span/position, metadata)

3. **Control flow**:
   - pipeline order (e.g., multiple tokenizers applied in sequence)
   - batch vs single-item APIs

4. **Error behavior**:
   - what raises exceptions vs what returns `None`/sentinel
   - which parsing failures are recoverable

Write this as a short bullet summary before coding.

---

## 1) Choose Scala representations (idiomatic + behavior-preserving)

### 1.1 Token types

Python commonly uses strings/constants/enums. In Scala 2.13, prefer a sealed hierarchy:

```scala
sealed trait TokenType { def name: String }
object TokenType {
  case object Word extends TokenType { val name = "word" }
  // ...
  val all: List[TokenType] = List(Word /*, ...*/)
  def fromString(s: String): Option[TokenType] =
    all.find(_.name.equalsIgnoreCase(s.trim))
}
```

Why: exhaustive matching, easy JSON/logging via `.name`.

### 1.2 Token value

If Python uses a flexible `value: Any`, keep Scala types explicit but extensible:

- If values are always strings: keep `value: String`.
- If values can be multiple types: use an ADT:

```scala
sealed trait TokenValue
object TokenValue {
  final case class Str(value: String) extends TokenValue
  final case class Num(value: BigDecimal) extends TokenValue
  final case class Time(value: java.time.Instant) extends TokenValue
}
```

### 1.3 Metadata

If Python attaches arbitrary metadata (dict), model as immutable:

```scala
type Metadata = Map[String, String]
```

If values are not just strings, use `Map[String, Any]` only if truly necessary; otherwise keep it typed.

---

## 2) Translate class hierarchy intentionally

### 2.1 Base classes / interfaces

Python base classes often define shared configuration + overridable methods.

In Scala:

- Use a `trait` if there’s no state.
- Use an `abstract class` if there is shared constructor state.

Example pattern:

```scala
trait BaseTokenizer {
  def tokenize(input: String): Vector[Token]
}
```

### 2.2 Composition over inheritance

If the Python code chains tokenizers (e.g., “universal tokenizer” delegating to specific ones), in Scala prefer composition:

```scala
final class UniversalTokenizer(parts: Vector[BaseTokenizer]) extends BaseTokenizer {
  override def tokenize(input: String): Vector[Token] =
    parts.flatMap(_.tokenize(input))
}
```

---

## 3) Error/absence mapping rules

Use these rules consistently:

- Python `None` → Scala `Option` (`None` / `Some(x)`).
- Python “try/except and continue” → Scala `Try(...).toOption` or `Either`.
- Python exceptions that should fail fast → Scala throw (rare) or return `Either[String, A]` for explicit errors.

Guideline:
- **Library-like** code: prefer `Either[String, A]` for user-visible failures.
- **Internal helpers**: `Option`/`Try` is fine to keep call sites clean.

---

## 4) Performance & scalability for massive data

Even in a single-file translation, you can keep things scalable:

- Precompile regex once:
  ```scala
  private val WordRe = "...".r
  ```
  or `new java.util.regex.Pattern` if you need flags.

- Use `Iterator` for streaming APIs when possible:
  - single input → `Vector[Token]` for deterministic materialization
  - batch input → `Iterator[Vector[Token]]` or `Vector[Vector[Token]]` depending on required signature

- Avoid quadratic concatenations (`++` in loops). Prefer builders:
  ```scala
  val b = Vector.newBuilder[Token]
  // b += token
  b.result()
  ```

---

## 5) Minimal Scala 2.13 “module skeleton” (copy & fill)

Use this structure to ensure compilation and readability.

```scala
import java.time.{Instant, LocalDate, ZoneOffset}
import scala.util.Try

// === Public model ===
sealed trait TokenType { def name: String }
object TokenType {
  // case objects ...
  def fromString(s: String): Option[TokenType] = None // fill
}

final case class Token(
  tokenType: TokenType,
  value: String,
  start: Option[Int] = None,
  end: Option[Int] = None,
  metadata: Map[String, String] = Map.empty
)

// === Tokenizers ===
trait BaseTokenizer {
  def tokenize(input: String): Vector[Token]

  // helper for consistent metadata updates
  protected final def withMetadata(t: Token, kv: (String, String)*): Token =
    t.copy(metadata = t.metadata ++ kv)
}

final class StringTokenizer(/* config */) extends BaseTokenizer {
  override def tokenize(input: String): Vector[Token] = Vector.empty
}

final class NumericTokenizer(/* config */) extends BaseTokenizer {
  override def tokenize(input: String): Vector[Token] = Vector.empty
}

final class TemporalTokenizer(/* config */) extends BaseTokenizer {
  override def tokenize(input: String): Vector[Token] = Vector.empty
}

final class UniversalTokenizer(parts: Vector[BaseTokenizer]) extends BaseTokenizer {
  override def tokenize(input: String): Vector[Token] =
    parts.flatMap(_.tokenize(input))
}

final class WhitespaceTokenizer extends BaseTokenizer {
  override def tokenize(input: String): Vector[Token] =
    input.split("\\s+").iterator.filter(_.nonEmpty).map { w =>
      Token(tokenType = ???, value = w)
    }.toVector
}

// === Builder / helpers ===
final case class TokenizerBuilder(
  // flags / config
) {
  def build(): BaseTokenizer = new WhitespaceTokenizer
}

object TokenizerApi {
  def toToken(/* python-equivalent args */): Token = ???

  def tokenize(input: String, tokenizer: BaseTokenizer): Vector[Token] =
    tokenizer.tokenize(input)

  def tokenizeBatch(inputs: Iterable[String], tokenizer: BaseTokenizer): Vector[Vector[Token]] =
    inputs.iterator.map(tokenizer.tokenize).toVector
}
```

Notes:
- Keep **all required names** present (classes + functions). If the prompt requires top-level functions, implement them as members of a Scala `object` with the same names.
- Prefer `final` for concrete classes; it communicates intent and helps performance.

---

## 6) Compilation readiness checklist (Scala 2.13)

Before concluding:

- No Scala 3 keywords (`enum`, `given`, `using`, `extension`).
- All referenced types are imported (`java.time`, `scala.util`, regex).
- No wildcard Java time imports that hide names.
- If you used regex, ensure it’s compiled once (as `val`).
- Ensure method signatures match the required API list.

If you cannot run `scalac` in the environment, still do a static sanity pass:

- Does every class/trait/object open/close braces correctly?
- Are there any `???` left?
- Are overloaded methods ambiguous?

---

## 7) Behavioral parity sanity checks

If tests are unavailable, create a minimal set of manual examples (in comments) based on the Python behavior:

- empty input
- whitespace-only
- mixed alphanumeric
- malformed numeric/temporal values (should recover or fail?)

These examples should be generic and **not copied from the benchmark instance**.
