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

### Python @overload and isinstance dispatch

When a Python function declares several `typing.overload` signatures and its
implementation dispatches on `isinstance(...)` over a *closed* set of input
types, the overloads are the specification of the public API surface, not
documentation. Translate them to Scala's *static* dispatch mechanisms and
reserve any `Any`-taking method for a documented lower-priority fallback.

Recipe (apply in order; stop at the first that fits):

1. **One overloaded Scala method per concrete `@overload` variant.** Let the
   compiler pick by parameter type/arity. This preserves type safety at every
   call site and eliminates runtime class checks.
2. **Model closed unions as a sealed ADT** (e.g. `str | bytes` →
   `sealed trait StringOrBytes { case class Str(...) ; case class Bytes(...) }`)
   and pattern-match exhaustively. The compiler warns on missing cases.
3. **Translate `@runtime_checkable` Protocol variants to a type class** (e.g.
   `trait Tokenizable[-A] { def toToken(a: A): String }`) with `implicit`
   instances, so user types opt in without nominal inheritance.
4. **Only if a genuine open-world fallback is required**, add a single
   `Any`-taking helper under a *distinct name* (e.g. `tokenizeAny`) so it does
   not shadow or ambiguate the typed overloads.

Anti-pattern — collapsing every `@overload` into one `def f(value: Any)` whose
body is a `match` on runtime classes (`String`, `Array[Byte]`, `Int`, `Long`,
`Double`, `LocalDate`, ..., catch-all `case other`). This loses static type
checking, forces callers through `Any`, and typically ambiguates any type-class
overload added later.

```python
# Python
@overload
def tokenize(self, value: str) -> Token: ...
@overload
def tokenize(self, value: int) -> Token: ...
@overload
def tokenize(self, value: datetime) -> Token: ...
@overload
def tokenize(self, value: Tokenizable) -> Token: ...

def tokenize(self, value: Any) -> Token:
    if isinstance(value, Tokenizable): ...
    if isinstance(value, (str, bytes)): ...
    if isinstance(value, (int, float, Decimal)): ...
    if isinstance(value, (datetime, date)): ...
    return Token(str(value), TokenType.STRING, {"fallback": True})
```

```scala
// Scala - one overload per concrete input type + ADT + type class
def tokenize(value: String): Token          = stringTokenizer.tokenize(value)
def tokenize(value: Long): Token             = numericTokenizer.tokenize(value)
def tokenize(value: Double): Token           = numericTokenizer.tokenize(value)
def tokenize(value: BigDecimal): Token       = numericTokenizer.tokenize(value)
def tokenize(value: LocalDate): Token        = temporalTokenizer.tokenize(value)
def tokenize(value: LocalDateTime): Token    = temporalTokenizer.tokenize(value)
def tokenize[A](value: A)(implicit ev: Tokenizable[A]): Token =
  Token(ev.toToken(value), TokenType.STRUCTURED)

// Reserve Any-dispatch only as a documented, distinctly named fallback.
def tokenizeAny(value: Any): Token = value match {
  case null                     => Token("NULL", TokenType.NULL)
  case s: String                => tokenize(s)
  case l: Long                  => tokenize(l)
  case d: Double                => tokenize(d)
  case dt: LocalDateTime        => tokenize(dt)
  case d: LocalDate             => tokenize(d)
  case other                    => Token(other.toString, TokenType.STRING, Map("fallback" -> true))
}
```

Verification before finishing the translation:
- Grep the produced Scala for `: Any)` in public method signatures; each
  occurrence must correspond to an intentional, distinctly named fallback and
  not shadow the typed overloads.
- Confirm each `@overload` signature in the Python source has a matching
  Scala method with a concrete parameter type (or is subsumed by a type-class
  overload).
- If a call `tokenize(x)` is ambiguous between the type-class overload and an
  `Any` overload, resolve it by renaming the `Any` method — **do not** weaken
  the type class to a subtype trait, which loses ad-hoc polymorphism for types
  the caller cannot modify.

Do not apply this recipe to Python functions that genuinely accept arbitrary
`object` with no `@overload` contract (e.g. `__repr__`-style debug helpers);
there a single `Any`/`AnyRef` method with a `match` is acceptable.

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
