---
name: python-scala-syntax-mapping
description: Reference guide for translating Python syntax and behavior to compile-safe Scala 2.13. Use when converting Python modules to Scala and preserving public APIs, control flow, collections, optional values, formatting, exceptions, and related semantics.
---

# Python to Scala Syntax Mapping

Translate behavior rather than syntax literally. Preserve every required public class, method, function name, parameter order, parameter type, default value, overload, and return type. For Python module-level functions, place them in a stable Scala `object` or other required API container because Scala 2.13 does not support ordinary top-level method definitions. Prefer clear Scala abstractions and standard-library operations over mechanical rewrites.

## Scala 2.13 Compile-Safety Workflow

1. Inventory all Python classes, functions, constructors, overloads, annotations, defaults, and externally visible members.
2. Choose Scala representations before translating bodies: `case class`, `sealed trait` plus case objects/classes, `Option`, collections, and a suitable companion object.
3. Preserve public signatures exactly as required by the source contract. Do not silently rename or change parameter order, defaults, visibility, or return shapes. For public tokenization-style APIs, including single-item conversion, batch processing, and metadata enrichment, verify each signature explicitly against the source specification.
4. Translate control flow and Python-specific behavior explicitly; do not assume Scala has Python's truthiness, `None`, `isinstance`, or floor-division semantics.
5. Add explicit result types where inference could produce an overly general type, an unintended `Any`, a widened collection, or an inaccessible implementation type.
6. Compile with Scala 2.13 and fix warnings or type mismatches before considering the translation complete. Exercise representative empty, missing, invalid, and boundary inputs.

## Variables and Type Annotations

| Python | Scala |
|--------|-------|
| `x = 5` | `val x = 5` (immutable) or `var x = 5` (mutable) |
| `x: int = 5` | `val x: Int = 5` |
| `x, y = 1, 2` | `val (x, y) = (1, 2)` |
| `def f(x: int) -> str` | `def f(x: Int): String = ...` |
| `x: Optional[T]` | `x: Option[T]` |

Prefer `val` over `var`; use `var` only when mutation is required. Scala method parameter defaults are written in the signature:

```scala
def greet(name: String, greeting: String = "Hello"): String =
  s"$greeting, $name!"
```

Keep default expressions equivalent to Python's defaults. Be careful with mutable default values: create a fresh collection per call rather than sharing one across calls.

## Type Mappings

| Python | Scala |
|--------|-------|
| `int` | `Int` or `Long` when the value can exceed `Int` range |
| `float` | `Double` |
| `str` | `String` |
| `bool` | `Boolean` |
| `None` | `None` as an `Option` value, usually represented by `Option.empty`; avoid `null` |
| `list[T]` | `List[T]`, `Seq[T]`, or another collection chosen for required operations |
| `dict[K, V]` | `Map[K, V]` |
| `set[T]` | `Set[T]` |
| `tuple[A, B]` | `(A, B)` or `Tuple2[A, B]` |
| `Optional[T]` | `Option[T]` |
| Python class with data fields | usually `case class` |
| Python tagged variants or enum-like values | `sealed trait` with case objects/case classes |

Do not use `null` merely to imitate Python `None`. Use `Option[T]` at API boundaries and make absence explicit in pattern matches or combinators.

## Classes, Constructors, Overloads, and Companion Objects

Python constructors and class-level factories commonly map to a Scala class or `case class` plus a companion object:

```scala
final case class Record(value: String, metadata: Map[String, String] = Map.empty)

object Record {
  def fromValue(value: String): Record = Record(value)
}
```

Use companion construction (`Record(...)`) for case classes rather than `new Record(...)` unless a normal class requires it. Put factory methods, constants, extractors, and module-level entry points in the companion object or a clearly named public object.

Scala does not support Python-style dynamic overloading. Define distinct Scala overloads with unambiguous parameter types, or use one method with an explicit algebraic data type when overloads would collide after erasure. Ensure overloads do not differ only by generic type arguments, because that can fail to compile on the JVM.

## Control Flow

### Conditionals

Scala `if` is an expression, so return or assign its value directly:

```python
if x > 0:
    result = "positive"
elif x < 0:
    result = "negative"
else:
    result = "zero"
```

```scala
val result: String =
  if (x > 0) "positive"
  else if (x < 0) "negative"
  else "zero"
```

Every branch should produce a compatible type. Add an explicit result type when branch inference might widen the result unexpectedly.

### Loops and Ranges

```python
for i in range(10):
    print(i)

for item in items:
    process(item)

for i, item in enumerate(items):
    print(f"{i}: {item}")
```

```scala
for (i <- 0 until 10) println(i)
for (item <- items) process(item)
for ((item, i) <- items.zipWithIndex) println(s"$i: $item")
```

Use `until` for Python's exclusive upper bound and `to` for an inclusive bound. Check step direction and empty-range behavior explicitly; use `by` where Python supplies a step. `zipWithIndex` produces `(element, index)`, so preserve the corresponding pattern order.

### While Loops

```python
while condition:
    do_something()
```

```scala
while (condition) {
  doSomething()
}
```

Because Scala `while` returns `Unit`, use a mutable accumulator only when the Python loop genuinely mutates state; otherwise prefer `foldLeft`, `map`, or another collection operation.

## Comprehensions and Collections

```python
squares = [x ** 2 for x in range(10)]
evens = [x for x in numbers if x % 2 == 0]
pairs = [(x, y) for x in xs for y in ys]
```

```scala
val squares: List[Int] = (0 until 10).map(x => x * x).toList
val evens = numbers.filter(_ % 2 == 0)
val pairs = for {
  x <- xs
  y <- ys
} yield (x, y)
```

Use:

- `map` for one output per input.
- `filter` for predicates.
- `flatMap` or a `for`-comprehension for nested iteration or optional results.
- `collect` for filtering and transforming with a partial function; include every intended case.
- `foldLeft` for an explicit accumulator.

Preserve the required collection type and ordering. Do not assume a Python list maps to a lazy or immutable Scala collection without checking the API contract.

## Functions and Lambdas

```python
def add(a: int, b: int) -> int:
    return a + b

square = lambda x: x ** 2
```

```scala
def add(a: Int, b: Int): Int = a + b

val square: Int => Int = x => x * x
// or: val square = (x: Int) => x * x
```

Give public methods explicit return types. This is especially important for recursive methods, overloaded methods, methods returning collections or `Option`, and methods whose branches have different concrete implementations.

Python keyword-style construction or calls do not have a direct Scala equivalent. Use named arguments only when they match the Scala parameter names and are stable public API, or provide a named factory method/companion constructor that makes the intended fields clear. Do not rely on argument position when the source behavior depends on keyword names.

## String Formatting

| Python | Scala |
|--------|-------|
| `f"Hello, {name}!"` | `s"Hello, $name!"` |
| `f"Value: {x:.2f}"` | `f"Value: $x%.2f"` |
| `f"{x + y}"` | `s"${x + y}"` |
| `str(value)` | `value.toString` or interpolation |

Use braces for expressions and `s` interpolation for ordinary values. Use `f` interpolation only when a format specifier is required, and verify numeric formatting and locale-sensitive behavior.

## Common Operators and Semantic Differences

| Python | Scala | Notes |
|--------|-------|-------|
| `**` | `math.pow(x, y)` | Returns floating-point; use integer arithmetic when exact integral results are required. |
| `//` | `Math.floorDiv(x, y)` for integral operands | Scala integer `/` truncates toward zero and is not floor division for negative values. |
| `%` | `%` | Check negative-number behavior if exact Python semantics matter. |
| `and`, `or`, `not` | `&&`, `||`, `!` | Operands must be Boolean; no general truthiness conversion. |
| `in` | `.contains()` | For maps, clarify whether membership means keys or entries. |
| `is` | reference identity only when truly intended | Do not replace Python identity checks with `==`; Scala `==` is null-safe value equality. |
| `==` | `==` | Usually value equality, including case classes and collections. |

Python truthiness must be translated explicitly. In Scala, `if (value)` is valid only for `Boolean`; use checks such as `value.nonEmpty`, `value != 0`, `option.isDefined`, or a domain-specific predicate. Do not treat an empty collection, zero, or `None` as interchangeable without confirming the Python behavior.

## Type Checks and Dispatch

Translate `isinstance`-style dispatch into pattern matching or an explicit type-safe hierarchy:

```python
if isinstance(value, str):
    return handle_text(value)
elif isinstance(value, int):
    return handle_number(value)
else:
    return handle_other(value)
```

```scala
val result = value match {
  case text: String => handleText(text)
  case number: Int  => handleNumber(number)
  case other        => handleOther(other)
}
```

Prefer matching on a sealed trait or case-class hierarchy over matching on unrelated runtime classes. Account for boxing, numeric widening, and erased generic types; a pattern such as `case xs: List[String]` cannot reliably test the element type at runtime.

## Regular Expressions and Conditions

Python regex tests such as `re.match`, `re.search`, or `re.fullmatch` must be mapped to the corresponding Scala/JVM behavior deliberately. Compile reusable expressions with `scala.util.matching.Regex`, and distinguish full matches from substring searches:

```scala
import scala.util.matching.Regex

val tokenPattern: Regex = "[A-Za-z]+".r
val isToken = tokenPattern.matches(value) // full match
val containsToken = tokenPattern.findFirstIn(value).nonEmpty // search
```

Do not substitute a plain `contains` check for a regex condition. Preserve escaping, anchors, capture-group behavior, case sensitivity, and the handling of invalid input.

## Optional and Missing Values

```python
if value is None:
    return default
return process(value)

result = value if value is not None else default
```

```scala
val result: Result = optionValue match {
  case Some(v) => process(v)
  case None    => default
}

val concise: Result = optionValue.map(process).getOrElse(default)
```

Use `Some(value)` only for a present value and `None` for absence. Avoid calling `.get`; use `map`, `flatMap`, `fold`, `getOrElse`, or pattern matching. If the Python code distinguishes a missing key from a present key containing a null-like value, model that distinction explicitly rather than collapsing it.

## Exception Handling and Errors

```python
try:
    result = risky_operation()
except ValueError as e:
    handle_error(e)
finally:
    cleanup()
```

```scala
try {
  val result = riskyOperation()
} catch {
  case e: IllegalArgumentException => handleError(e)
} finally {
  cleanup()
}
```

Python and Scala exception classes differ. Map exception categories by behavior, not by name, and preserve cleanup with `finally` or a resource-safe abstraction. For recoverable functional errors:

```scala
import scala.util.{Try, Success, Failure}

val result: Result = Try(riskyOperation()) match {
  case Success(value) => value
  case Failure(error) => handleError(error)
}
```

Do not catch `Throwable` or broadly swallow failures unless the source contract requires it. Make invalid input, parse failures, and absent values explicit in return types where appropriate.

## Public API and Verification Checklist

Before finalizing a translation, verify:

- All required source classes, methods, constructors, factories, and module-level functions exist.
- Public names, visibility, parameter order, parameter types, default parameters, overloads, and return types match the contract exactly.
- Scala 2.13 syntax and imports are used; no Scala 3-only features are required.
- Module-level functions are reachable through the expected stable object or companion.
- Companion-object construction and case-class behavior match the intended constructor semantics.
- `None`/`Optional` values use `Option`, and no accidental `.get` or `null` remains.
- `isinstance`, truthiness, regex matching, integer division, and exception paths have explicit Scala equivalents.
- `range`, `enumerate`, comprehensions, ordering, and empty-input behavior are preserved.
- Public methods with fragile inference have explicit result types.
- The source compiles under Scala 2.13, and representative normal, empty, missing, malformed, and boundary cases have been exercised.
