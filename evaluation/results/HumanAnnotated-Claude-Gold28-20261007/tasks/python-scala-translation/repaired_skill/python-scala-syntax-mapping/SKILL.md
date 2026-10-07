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

## Required project check for a supplied Python module

Apply the translation workflow in `python-scala-idioms` before using these syntax mappings. Establish the source and consumer contract with actual tool output before writing the translation.

For a module delivered as `/root/Tokenizer.py`, first read its sibling public `/root/build.sbt` and `/root/TokenizerSpec.scala` in full. Extract the package declaration and public calls from that test file. Implement the translation in that package with compatible callable signatures. List all Python class/function definitions and map every one to the output; the source module defines the complete inventory even when the task's parenthetical enumeration is shorter. Save this mapping as `/root/translation-inventory.md`, and resolve missing entries before finishing.

After writing `/root/Tokenizer.scala`, test that exact file in an isolated project using the supplied, unchanged build and public tests. This avoids accidentally testing an existing reference implementation in a populated project:

```bash
set -euo pipefail
check_dir=$(mktemp -d /tmp/translation-check.XXXXXX)
mkdir -p "$check_dir/src/main/scala" "$check_dir/src/test/scala" "$check_dir/project"
cp /root/build.sbt "$check_dir/build.sbt"
cp /root/localtest/project/build.properties "$check_dir/project/build.properties"
cp /root/Tokenizer.scala "$check_dir/src/main/scala/Tokenizer.scala"
cp /root/TokenizerSpec.scala "$check_dir/src/test/scala/TokenizerSpec.scala"
(cd "$check_dir" && sbt clean test) 2>&1 | tee /root/translation-validation.log
```

Inspect the actual test summary: success requires tests to run and pass, not just source compilation or zero tests. When a package, missing type, method signature or behavior error occurs, repair the deliverable and repeat the copy-and-test step. Keep the original test/build files intact. End only after the complete source inventory is accounted for and this project check passes; if a dependency prevents it, report the concrete limitation. A self-written smoke test cannot satisfy this project check.
