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



Scala `for`-comprehensions can express nested loops, filtering, and transformations similarly to Python comprehensions.

```python
# Python
mapping = {x: x ** 2 for x in nums if x > 0}
unique = {x.lower() for x in words}
flattened = [y for xs in batches for y in xs]
```

```scala
// Scala
val mapping: Map[Int, Int] =
  nums.filter(_ > 0).map(x => x -> (x * x)).toMap

val unique: Set[String] = words.map(_.toLowerCase).toSet

val flattened = for {
  xs <- batches
  y <- xs
} yield y
```

Use `yield` when the comprehension should return a collection.
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




### Scala 2.13 file organization

Scala 2.13 does not support arbitrary top-level function definitions in the same way as Python modules or Scala 3. When translating a Python module, place free functions inside an `object`.

```scala
// Tokenizer.scala
sealed trait TokenType
final case class Token(text: String)

object Tokenizer {
  def tokenize(input: String): Seq[Token] = Seq.empty
  def tokenizeBatch(inputs: Seq[String]): Seq[Seq[Token]] = inputs.map(tokenize)
  def toToken(text: String): Token = Token(text)
}
```

Guidelines:
- Preserve required public method names and signatures exactly.
- Add explicit public return types for methods used by tests.
- Prefer companion objects for factory/helper methods.
- Map Python dataclasses to `case class` and enums to `sealed trait` + `case object` values.
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



Named arguments map directly to Scala and are useful when preserving Python call sites.

```python
# Python
greet(name="Alice", greeting="Hi")
```

```scala
// Scala
greet(name = "Alice", greeting = "Hi")
```
## String Formatting




## Indexing and Slicing

| Python | Scala |
|--------|-------|
| `items[0]` | `items(0)` |
| `items[-1]` | `items.last` |
| `text[1:4]` | `text.slice(1, 4)` |
| `items[:3]` | `items.take(3)` |
| `items[3:]` | `items.drop(3)` |
| `items[::-1]` | `items.reverse` |

```python
# Python
first, rest = values[0], values[1:]
```

```scala
// Scala
val first = values.head
val rest = values.tail
```
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
