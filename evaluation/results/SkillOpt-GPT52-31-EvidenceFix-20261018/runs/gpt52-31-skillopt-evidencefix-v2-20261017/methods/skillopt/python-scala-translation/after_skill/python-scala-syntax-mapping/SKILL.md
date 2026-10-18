---
name: python-scala-syntax-mapping
description: Reference guide for translating Python syntax constructs to Scala equivalents. Use when converting Python code to Scala and need mappings for basic syntax elements like variable declarations, control flow, comprehensions, string formatting, and common operators.
---

# Python to Scala Syntax Mapping

## Variable Declarations

| Python | Scala |
|--------|-------|
| `x = 5` | `val x = 5` (immutable) or `var x = 5` (mutable) |
| `x: int = 5` | `val x: Int = 5` |
| `x, y = 1, 2` | `val (x, y) = (1, 2)` |

Prefer `val` over `var` unless mutation is required.

## Type Mappings

| Python | Scala |
|--------|-------|
| `int` | `Int` |
| `float` | `Double` |
| `str` | `String` |
| `bool` | `Boolean` |
| `None` | Prefer `None`/`Option[T]`; use `null` only for Java interop or when the original API contract requires nullable values |
| `list[T]` | `List[T]` or `Seq[T]` |
| `dict[K, V]` | `Map[K, V]` |
| `set[T]` | `Set[T]` |
| `tuple[A, B]` | `(A, B)` or `Tuple2[A, B]` |
| `Optional[T]` | `Option[T]` |

## Control Flow

### Conditionals

```python
# Python
if x > 0:
    result = "positive"
elif x < 0:
    result = "negative"
else:
    result = "zero"
```

```scala
// Scala - if is an expression
val result = if (x > 0) "positive"
             else if (x < 0) "negative"
             else "zero"
```

### Loops

```python
# Python for loop
for i in range(10):
    print(i)

for item in items:
    process(item)

for i, item in enumerate(items):
    print(f"{i}: {item}")
```

```scala
// Scala equivalents
for (i <- 0 until 10) println(i)

for (item <- items) process(item)

for ((item, i) <- items.zipWithIndex) println(s"$i: $item")
```

### While loops

```python
# Python
while condition:
    do_something()
```

```scala
// Scala
while (condition) {
  doSomething()
}
```

## Comprehensions

```python
# Python list comprehension
squares = [x ** 2 for x in range(10)]
evens = [x for x in numbers if x % 2 == 0]
pairs = [(x, y) for x in xs for y in ys]
```

```scala
// Scala for-comprehensions or map/filter
val squares = (0 until 10).map(x => x * x).toList
val evens = numbers.filter(_ % 2 == 0)
val pairs = for { x <- xs; y <- ys } yield (x, y)
```

## Functions

```python
# Python
def add(a: int, b: int) -> int:
    return a + b

# Lambda
square = lambda x: x ** 2

# Default arguments
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"
```

```scala
// Scala
def add(a: Int, b: Int): Int = a + b

// Lambda
val square: Int => Int = x => x * x
// or shorter: val square = (x: Int) => x * x

// Default arguments
def greet(name: String, greeting: String = "Hello"): String =
  s"$greeting, $name!"
```

## String Formatting

| Python | Scala |
|--------|-------|
| `f"Hello, {name}!"` | `s"Hello, $name!"` |
| `f"Value: {x:.2f}"` | `f"Value: $x%.2f"` |
| `f"{x + y}"` | `s"${x + y}"` |

## Common Operators


### Integer Division Parity (Scala 2.13)

Python has both `/` (true division) and `//` (floor division). Scala’s `/` on `Int`/`Long` truncates toward **zero**, which differs from Python `//` for negative numbers.

```python
# Python
-3 // 2   # -2
-3 / 2    # -1.5
```

```scala
// Scala 2.13
-3 / 2          // -1  (truncates toward 0)  != Python //
Math.floorDiv(-3, 2)  // -2  (matches Python // for Int/Long)

-3.0 / 2        // -1.5
```

Use `Math.floorDiv(a, b)` for `Int`/`Long` when translating Python `//`.
| Python | Scala |
|--------|-------|
| `**` (power) | `math.pow(x, y)` or use `scala.math.pow` |
| `//` (floor div) | `x / y` (for Int) or `math.floor(x / y)` |
| `%` (modulo) | `%` |
| `and`, `or`, `not` | `&&`, `||`, `!` |
| `in` | `.contains()` |
| `is` | `eq` (reference equality) |
| `==` | `==` (value equality) |

## Exception Handling

```python
# Python
try:
    result = risky_operation()
except ValueError as e:
    handle_error(e)
finally:
    cleanup()
```

```scala
// Scala
import scala.util.{Try, Success, Failure}

// Pattern 1: try-catch
try {
  val result = riskyOperation()
} catch {
  case e: IllegalArgumentException => handleError(e)
} finally {
  cleanup()
}

// Pattern 2: Try monad (preferred for functional style)
val result = Try(riskyOperation()) match {
  case Success(value) => value
  case Failure(e) => handleError(e)
}
```

## None/Null Handling


### Option vs null (behavioral pitfalls)

Avoid mixing `Option` and `null` in the same public API. If Python can return `None`, prefer `Option[T]` end-to-end.

Bridging rules:

```scala
// From possibly-null (Java) to Option
val opt: Option[String] = Option(maybeNullString)

// From Option back to nullable (only at interop boundaries)
val nullable: String = opt.orNull
```

Never call `.get` on `Option` unless the Python code would have thrown at that point; prefer `getOrElse`, `fold`, or pattern matching.

### Laziness: Iterator/View/LazyList vs eager collections

Python generators are lazy; many Scala collection ops are eager.

- Use `Iterator` for one-pass, streaming pipelines (closest to Python generators).
- Use `.view` for lazy transforms over an existing strict collection.
- Use `LazyList` for potentially infinite sequences.

```scala
val it = lines.iterator.map(_.trim).filter(_.nonEmpty) // lazy
val first100 = it.take(100).toList                     // materialize explicitly

val v = lines.view.map(_.trim).filter(_.nonEmpty)      // lazy view
val out = v.take(100).toList
```

Pitfall: `Iterator` is single-use; don’t reuse it if Python iterated multiple times.

### Regex and split differences (Scala/JVM)

Scala `String#split` uses **Java regex**, not a literal delimiter.

```python
# Python
"a.b".split(".")   # ['a', 'b']  (literal dot)
```

```scala
// Scala/Java: dot is "any char" in regex; must escape for literal dot
"a.b".split("\\.")  // Array("a", "b")
```

Also note:
- Backslashes need double escaping in normal Scala strings.
- Prefer `raw"..."` for complex regex literals.
- Java/Scala regex features and flags differ from Python `re` (test equivalence).

### Module-level functions → Scala objects (exported names)

Python module-level functions should be placed in an `object` in Scala.

```scala
object Tokenizer {
  def tokenize(...): ... = ...
  def tokenizeBatch(...): ... = ...
  def toToken(...): ... = ...
  def withMetadata(...): ... = ...
}
```

Hidden tests often require exact exported names/signatures; keep them stable.

### Default parameters and varargs

Scala supports default parameters, but overloads + defaults can cause ambiguous calls.
Prefer a single definition with defaults.

For Python `*args` / varargs:

```scala
def withMetadata(kv: (String, String)*): Token = ...
// forwarding varargs requires : _*
other.withMetadata(kv: _*)
```

### Collection conversion & ordering semantics

Python `dict` preserves insertion order (3.7+). Scala’s default immutable `Map` does **not** guarantee iteration order.
- If order matters, use `ListMap` (small) or preserve an explicit `List[(K,V)]`.

Be explicit when converting:
- `iterator.toList` materializes now (like `list(...)` in Python)
- `map.view.mapValues(...)` is lazy in Scala 2.13; call `.toMap` to force

```scala
val strict = m.view.mapValues(f).toMap
```
```python
# Python
if value is None:
    return default
return process(value)

# Or
result = value if value is not None else default
```

```scala
// Scala - use Option
val result = optionValue match {
  case Some(v) => process(v)
  case None => default
}

// Or more concisely
val result = optionValue.map(process).getOrElse(default)
```



## Scala 2.13 Behavioral Parity Checklist (hidden-test focused)

Before finalizing a Python→Scala translation, verify:

- **Exported API surface:** required classes/objects/defs exist with exact names and call shapes (including defaults).
- **None/null contract:** `None` in Python maps to `Option` (or nullable) consistently; no accidental `.get`/NPE.
- **Laziness:** generator-like code stays lazy (`Iterator`/`view`/`LazyList`); avoid unintended `.toList` materialization.
- **Regex/split:** delimiter and regex escaping match Python behavior; edge cases (empty fields, leading/trailing separators) are tested.
- **Numeric semantics:** integer division matches (`Math.floorDiv` for Python `//`); conversions/rounding match.
- **Collections:** ordering guarantees are preserved when required; mutability is explicit (`mutable` only when needed).
- **Single-pass vs multi-pass:** `Iterator` isn’t reused; if Python iterates twice, materialize or recreate.
- **Interop boundaries:** any `null` usage is confined to Java interop edges; internal logic uses `Option`/`Either`.
