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



## Scala 2.13 Translation and Compilation Checklist

When translating a complete Python module such as a tokenizer, treat these mappings as implementation constraints rather than literal syntax substitutions. Compile with Scala 2.13 early and often, and give public classes, methods, and module-entry functions explicit result types when inference could obscure an accidental `Unit`, `Any`, widened collection type, or incorrect tuple shape.

### Python defaults, keyword-like construction, and data models

Scala supports default parameters and named arguments only for parameters declared by the method or constructor; it does not support arbitrary Python `**kwargs` construction. Translate a Python function default directly when it is a stable value, for example `def f(x: String, mode: String = "default"): Result = ...`. For a Python dataclass, prefer a `case class` with typed fields, constructor defaults where appropriate, and `copy` for immutable updates. Do not assume that Python's positional and keyword calls are interchangeable: preserve the source meaning with named Scala arguments or an explicit builder/configuration case class.

For Python enums, use a sealed hierarchy (`sealed trait TokenType` with `case object` values) when exhaustive pattern matching is useful, or a Scala `Enumeration` only when its limitations are acceptable. A sealed hierarchy is generally clearer for tokenizer dispatch. Put companion-level factories and constants in the companion object.

Python module-level functions cannot be declared at top level in Scala 2.13. Place functions such as `tokenize`, `tokenizeBatch`, `toToken`, and `withMetadata` in a named `object` (or in an appropriate companion object), with explicit parameter and return types. A Python `@staticmethod` normally becomes a method on an object; a `@classmethod` usually becomes a companion-object factory or method. Keep instance state and object-level utilities separate.

### Dispatch and type checks

Translate `isinstance(value, T)` primarily with sealed-trait pattern matching:

```scala
value match {
  case s: String => handleString(s)
  case n: Number => handleNumber(n)
  case _ => handleOther(value)
}
```

Use `isInstanceOf[T]` only when a boolean test is genuinely required, followed by a safe cast or a better pattern match. Do not use `isInstanceOf[List[String]]` as if generic arguments were checked at runtime; type erasure prevents that. For tokenizer subclasses, prefer polymorphic methods or exhaustive matching over a long chain of dynamic checks.

### None, truthiness, and safe access

Python `None` maps to `Option[T]`: use `Some(value)` and `None`, then `map`, `flatMap`, `fold`, `getOrElse`, or pattern matching. Avoid `.get`, unchecked casts, and pervasive `null`. Convert nullable Java inputs at the boundary with `Option(value)` when appropriate.

Scala does not treat empty strings, zero, empty collections, or `None` as a general false value. Translate each Python truthiness test into the intended predicate, such as `s.nonEmpty`, `xs.nonEmpty`, `n != 0`, or `option.nonEmpty`; use `option.isDefined`/pattern matching for presence. Preserve short-circuiting with `&&`, `||`, and `!`, and remember that `==` is value equality while `eq` is reference identity.

### Exceptions, parsing, and failure policy

A Python `try/except/finally` can remain a Scala `try`/`catch`/`finally` when cleanup and imperative control flow are clearest. Match concrete exception types, and do not catch `Throwable` merely to make translation succeed. For a value-oriented API, use `scala.util.Try` and explicitly match `Success` and `Failure`, or return `Either[Error, Result]` when callers need a typed error. `scala.util.Using` is suitable for closeable resources in Scala 2.13.

Decide the parsing contract before translating exception behavior. A recognizer that tests whether input belongs to another token type should represent an expected non-match as `None`, an empty result, or `false`, according to its declared API; it must not throw for ordinary non-matching input. Malformed input, violated invariants, unsupported syntax, I/O failures, or programmer errors should be propagated or represented as an explicit failure rather than silently converted into a non-match. Document this distinction in return types and preserve the Python behavior for each tokenizer path.

### Strings, interpolation, regular expressions, and indexing

Translate f-strings with `s"...$name..."` or `s"...${expression}..."`; use the `f` interpolator only when a numeric format is required, for example `f"value: $x%.2f"`. Expressions containing punctuation or operators need braces. Escape literal dollar signs as required by Scala interpolation.

Use `scala.util.matching.Regex` (often via a raw interpolator such as `"...".r`) and choose the operation that matches Python semantics: `findFirstIn`/`findAllIn` for searching, anchored patterns or `matches` for whole-string matching, and `unapplySeq` for capture groups. Do not silently replace Python `re.search` with a whole-string match.

Python string indexing and slicing require explicit bounds in Scala. Use `s.charAt(i)` or `s(i)` for a character, `s.substring(from, until)`, or `s.slice(from, until)` for a range. Implement negative-index behavior deliberately because Scala does not automatically give Python's negative indexing semantics. Be aware that indexing a `String` returns a UTF-16 `Char`, not necessarily a full Unicode code point.

### Collections, comprehensions, generators, and tuple order

Translate list comprehensions with `map`, `filter`, and `flatMap` or a `for` expression. Preserve nesting order: `for (x <- xs; y <- ys) yield (x, y)` corresponds to Python's outer `x` and inner `y`. Python generators should become a lazy `Iterator`, `View`, or an explicitly documented strict collection; do not materialize massive tokenizer data accidentally.

`enumerate(items)` yields `(index, item)` in Python, while `items.zipWithIndex` yields `(item, index)` in Scala. Destructure and construct tuples accordingly, and keep this order consistent in every public API. `xs.zip(ys)` truncates to the shorter input, matching ordinary Python `zip`; use an explicit length check or another strategy if the source requires a mismatch error. Prefer `0 until n` for Python `range(n)` and distinguish `until` from inclusive `to`.

### Scala 2.13 build checks

Use valid Scala 2.13 collection APIs and imports, avoid Python-only syntax, and ensure every branch of an `if` or `match` has a compatible type. Check that case-class companion `apply` calls, overloaded constructors, regex patterns, exception classes, and collection element types compile without unintended widening. Confirm that all required tokenizer classes (`TokenType`, `Token`, `BaseTokenizer`, concrete tokenizers, and `TokenizerBuilder`) have coherent visibility, inheritance, and return types, and that object methods expose the required module-level functionality. Run the compiler and representative tests after each structural translation rather than relying on visual similarity to the Python source.
