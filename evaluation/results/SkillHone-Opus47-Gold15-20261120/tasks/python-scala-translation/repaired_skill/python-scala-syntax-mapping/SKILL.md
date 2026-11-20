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
| `None` | `None` (of type `Option`) or `null` |
| `list[T]` | `List[T]` or `Seq[T]` |
| `dict[K, V]` | `Map[K, V]` |
| `set[T]` | `Set[T]` |
| `tuple[A, B]` | `(A, B)` or `Tuple2[A, B]` |
| `Optional[T]` | `Option[T]` |

### Union Types (`A | B`) in Scala 2.13

Scala 2.13 does **not** support `A | B` union types (only Scala 3 does).
Translation options, in rough order of preference when the goal is to keep
the public API usable:

1. **Method overloads** on the owning class/object. Keeps `handle("hi")`
   and `handle(byteArray)` callable with their native types.
2. **`Any`-typed parameter with a pattern-match dispatch**. Preferred when
   the Python code already uses `isinstance` dispatch and the caller passes
   heterogeneous values.
3. **Sealed ADT wrapper**. Only when the union itself is a conceptual domain
   type (`enum`-like). Wrapping every union silently forces callers to
   adopt the new type, which is a common source of translation regressions.

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

### Dynamic precision in the `f""` interpolator

Scala's `f""` interpolator parses the format specifier at compile time, so it
**cannot** embed a value inside `%...f` the way Python's f-string can:

```scala
// Python
f"{value:.{precision}f}"

// Scala - DOES NOT COMPILE
f"$value%.${precision}f"
// error: Missing conversion operator in '%'; use %% for literal %, %n for newline
```

Use `String.format` with a pre-built pattern instead:

```scala
String.format(s"%.${precision}f", java.lang.Double.valueOf(value))
// or:
s"%.${precision}f".format(value)   // on a plain String
```

For `BigDecimal`, call `setScale(precision, RoundingMode.HALF_UP)` and then
`.toString` to keep the exact Python rounding semantics.

## `type(x).__name__` and Runtime Class Names

Python's `type(value).__name__` returns the runtime class name as a plain
string. **The Scala idiomatic default is to report Scala class names**
(`"Int"`, `"Double"`, `"BigDecimal"`, …), not the Python spellings, because
the rest of the Scala codebase (pattern matches, downstream switches, test
assertions) is written against Scala names.

Check the project's test spec first: if it asserts
`metadata should contain ("original_type" -> "Int")` or passes a Scala
`BigDecimal` and expects `"BigDecimal"`, use Scala names. Only switch to
Python spellings (`"int"`, `"float"`, `"Decimal"`) when you have concrete
evidence (test assertion, downstream consumer, prompt requirement) that
demands them.

```scala
// Default: Scala names via explicit pattern match so you choose the exact
// spelling rather than relying on JVM boxing (which yields "Integer", etc.).
val originalType = value match {
  case _: Int        => "Int"
  case _: Long       => "Long"
  case _: Float      => "Float"
  case _: Double     => "Double"
  case _: BigDecimal => "BigDecimal"
  case other         => other.getClass.getSimpleName
}
```

The equivalent Python-name table, for the rare case the spec demands it:

```scala
val originalTypePython = value match {
  case _: Int        => "int"
  case _: Long       => "int"
  case _: Float      => "float"
  case _: Double     => "float"
  case _: BigDecimal => "Decimal"
  case other         => other.getClass.getSimpleName
}
```

Raw `value.getClass.getSimpleName` returns JVM-boxed names (`"Integer"`,
`"Double"`, `"BigDecimal"`) — fine for `BigDecimal` but wrong for `Int`,
which boxes to `"Integer"`. Prefer the explicit pattern match above.

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
