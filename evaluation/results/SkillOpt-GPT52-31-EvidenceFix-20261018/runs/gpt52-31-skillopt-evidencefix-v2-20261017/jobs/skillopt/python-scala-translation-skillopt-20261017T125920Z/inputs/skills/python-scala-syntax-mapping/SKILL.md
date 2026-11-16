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



## Scala 2.13 Translation Pitfalls

### None, null, and Option

Python `None` most often maps to `Option[T]` in Scala rather than raw `null`.

```python
# Python
value = None
if value is None:
    return default
```

```scala
// Preferred Scala style
val value: Option[String] = None
value.getOrElse(default)
```

Use `null` only when interoperating with Java APIs or when the original API contract explicitly requires it. Avoid mixing `null` and `Option` in the same interface.

### Module-level Functions vs Scala Objects

Python modules commonly expose top-level functions:

```python
# tokenizer.py
def tokenize(text):
    ...
```

Scala 2.13 does not support arbitrary top-level defs in the same way. Put shared functions into an `object` (or package object when required by the project structure).

```scala
object Tokenizer {
  def tokenize(text: String): Seq[String] = ???
}
```

When a task requires specific exported names, ensure the object and method names exactly match the expected API shape.

### Regex and split Differences

Python and Scala/JVM regex handling differ because Scala uses Java regex syntax.

```python
# Python
parts = text.split(".")
```

```scala
// Scala/Java regex split: dot must be escaped
val parts = text.split("\\.")
```

Common pitfalls:
- `split` uses regex, not literal strings
- Backslashes usually need double escaping inside Scala strings
- Prefer raw interpolation for complex regex: `raw"\\d+".r`
- Python regex helpers may need explicit `.r` conversion in Scala

### Iterator/Generator Laziness

Python generators are lazy by default.

```python
def values():
    for x in data:
        yield x
```

Scala collections like `List.map` are strict. Use `Iterator`, `LazyList`, or views when preserving laziness matters.

```scala
def values(data: Seq[Int]): Iterator[Int] =
  data.iterator.map(_ * 2)
```

Be careful not to accidentally materialize large collections with `.toList` or `.toSeq` if the Python version streamed results lazily.

### Default Arguments and Overloads

Python often relies heavily on optional parameters.

```python
def greet(name, prefix="Hello"):
    ...
```

```scala
def greet(name: String, prefix: String = "Hello"): String =
  s"$prefix $name"
```

Scala supports default parameters, but overloaded methods plus defaults can create ambiguous calls. Prefer one method with defaults unless multiple signatures are explicitly required.

### Integer Division and String Formatting

Python and Scala integer semantics differ in subtle edge cases.

```python
5 // 2   # 2
5 / 2    # 2.5
```

```scala
5 / 2         // 2 (Int division)
5.0 / 2       // 2.5
math.floor(x / y)
```

String interpolation mappings:
- Python `f"{x}"` → Scala `s"$x"`
- Python formatted floats → Scala `f"$x%.2f"`
- Use `${expr}` for expressions inside interpolated strings

### Common Scala Compile Pitfalls

- `@tailrec` only compiles when recursion is truly tail-recursive
- Methods inside classes/objects must be ordered and scoped correctly
- Avoid defining a `val` and `def` with the same name in the same scope
- Overloaded defs may require explicit parameter types to avoid ambiguity
- Case classes automatically generate companion objects; avoid conflicting manual definitions
- Public method signatures must exactly match required evaluator/test expectations
- Scala collections are immutable by default; mutating translations may require `mutable` collections explicitly

### Behavioral Parity Checklist

Before finalizing a Python→Scala translation, verify:
- `None`/missing values preserve the same runtime behavior
- Laziness vs eager evaluation matches the original implementation
- Regex and `split` semantics are equivalent
- Default argument behavior matches Python call sites
- Integer division and numeric conversions behave identically
- Exported method/class/object names exactly match the required API
- Collection ordering and mutability semantics are preserved
- The Scala code compiles cleanly under Scala 2.13
