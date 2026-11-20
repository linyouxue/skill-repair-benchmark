---
name: python-scala-functional
description: Guide for translating Python code to functional Scala style. Use when converting Python code involving higher-order functions, decorators, closures, generators, or when aiming for idiomatic functional Scala with pattern matching, Option handling, and monadic operations.
---

# Python to Scala Functional Programming Translation

## Higher-Order Functions

```python
# Python
def apply_twice(f, x):
    return f(f(x))

def make_multiplier(n):
    return lambda x: x * n

double = make_multiplier(2)
result = apply_twice(double, 5)  # 20
```

```scala
// Scala
def applyTwice[A](f: A => A, x: A): A = f(f(x))

def makeMultiplier(n: Int): Int => Int = x => x * n

val double = makeMultiplier(2)
val result = applyTwice(double, 5)  // 20
```

## Decorators → Function Composition

```python
# Python
def log_calls(func):
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__}")
        result = func(*args, **kwargs)
        print(f"Finished {func.__name__}")
        return result
    return wrapper

@log_calls
def add(a, b):
    return a + b
```

```scala
// Scala - function composition
def logCalls[A, B](f: A => B, name: String): A => B = { a =>
  println(s"Calling $name")
  val result = f(a)
  println(s"Finished $name")
  result
}

val add = (a: Int, b: Int) => a + b
val loggedAdd = logCalls(add.tupled, "add")

// Alternative: using by-name parameters
def withLogging[A](name: String)(block: => A): A = {
  println(s"Calling $name")
  val result = block
  println(s"Finished $name")
  result
}
```

## Pattern Matching

```python
# Python (3.10+)
def describe(value):
    match value:
        case 0:
            return "zero"
        case int(x) if x > 0:
            return "positive int"
        case int(x):
            return "negative int"
        case [x, y]:
            return f"pair: {x}, {y}"
        case {"name": name, "age": age}:
            return f"{name} is {age}"
        case _:
            return "unknown"
```

```scala
// Scala - pattern matching is more powerful
def describe(value: Any): String = value match {
  case 0 => "zero"
  case x: Int if x > 0 => "positive int"
  case _: Int => "negative int"
  case (x, y) => s"pair: $x, $y"
  case List(x, y) => s"list of two: $x, $y"
  case m: Map[_, _] if m.contains("name") =>
    s"${m("name")} is ${m("age")}"
  case _ => "unknown"
}

// Case class pattern matching (preferred)
sealed trait Result
case class Success(value: Int) extends Result
case class Error(message: String) extends Result

def handle(result: Result): String = result match {
  case Success(v) if v > 100 => s"Big success: $v"
  case Success(v) => s"Success: $v"
  case Error(msg) => s"Failed: $msg"
}
```

## Option Handling (None/null Safety)

```python
# Python
def find_user(user_id: int) -> Optional[User]:
    user = db.get(user_id)
    return user if user else None

def get_user_email(user_id: int) -> Optional[str]:
    user = find_user(user_id)
    if user is None:
        return None
    return user.email

# Chained operations
def get_user_city(user_id: int) -> Optional[str]:
    user = find_user(user_id)
    if user is None:
        return None
    address = user.address
    if address is None:
        return None
    return address.city
```

```scala
// Scala - Option monad
def findUser(userId: Int): Option[User] = db.get(userId)

def getUserEmail(userId: Int): Option[String] =
  findUser(userId).map(_.email)

// Chained operations with flatMap
def getUserCity(userId: Int): Option[String] =
  findUser(userId)
    .flatMap(_.address)
    .map(_.city)

// For-comprehension (cleaner for multiple operations)
def getUserCity(userId: Int): Option[String] = for {
  user <- findUser(userId)
  address <- user.address
  city <- Option(address.city)
} yield city

// Getting values out
val email = getUserEmail(1).getOrElse("no-email@example.com")
val emailOrThrow = getUserEmail(1).get  // Throws if None
```

## Generators → Iterators/LazyList

```python
# Python
def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

# Take first 10
fibs = list(itertools.islice(fibonacci(), 10))
```

```scala
// Scala - LazyList (was Stream in Scala 2.12)
def fibonacci: LazyList[BigInt] = {
  def loop(a: BigInt, b: BigInt): LazyList[BigInt] =
    a #:: loop(b, a + b)
  loop(0, 1)
}

val fibs = fibonacci.take(10).toList

// Alternative: Iterator
def fibonacciIterator: Iterator[BigInt] = new Iterator[BigInt] {
  private var (a, b) = (BigInt(0), BigInt(1))
  def hasNext: Boolean = true
  def next(): BigInt = {
    val result = a
    val newB = a + b
    a = b
    b = newB
    result
  }
}
```

## Try/Either for Error Handling

```python
# Python - exceptions
def parse_int(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        return 0

# Python - Optional for errors
def safe_parse_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except ValueError:
        return None
```

```scala
// Scala - Try monad
import scala.util.{Try, Success, Failure}

def parseInt(s: String): Try[Int] = Try(s.toInt)

val result = parseInt("123") match {
  case Success(n) => s"Got: $n"
  case Failure(e) => s"Error: ${e.getMessage}"
}

// Chaining Try operations
val doubled = parseInt("123").map(_ * 2)

// Either for custom error types
def parsePositive(s: String): Either[String, Int] = {
  Try(s.toInt).toEither
    .left.map(_ => "Not a number")
    .flatMap { n =>
      if (n > 0) Right(n)
      else Left("Must be positive")
    }
}
```

## Function Composition

```python
# Python
def compose(f, g):
    return lambda x: f(g(x))

def pipe(*functions):
    def inner(x):
        result = x
        for f in functions:
            result = f(result)
        return result
    return inner

# Usage
add_one = lambda x: x + 1
double = lambda x: x * 2
pipeline = pipe(add_one, double, add_one)  # (x + 1) * 2 + 1
```

```scala
// Scala - built-in composition
val addOne: Int => Int = _ + 1
val double: Int => Int = _ * 2

// compose: f.compose(g) = f(g(x))
val composed = addOne.compose(double)  // addOne(double(x))

// andThen: f.andThen(g) = g(f(x))
val pipeline = addOne.andThen(double).andThen(addOne)  // (x + 1) * 2 + 1
```

## Currying and Partial Application

```python
# Python
from functools import partial

def add(a, b, c):
    return a + b + c

add_5 = partial(add, 5)
result = add_5(3, 2)  # 10
```

```scala
// Scala - curried functions
def add(a: Int)(b: Int)(c: Int): Int = a + b + c

val add5 = add(5) _  // Partially applied
val result = add5(3)(2)  // 10

// Converting between curried and uncurried
val uncurried = Function.uncurried(add _)
val curried = (uncurried _).curried

// Multiple parameter lists
def fold[A, B](init: B)(list: List[A])(f: (B, A) => B): B =
  list.foldLeft(init)(f)

val sum = fold(0)(List(1, 2, 3))(_ + _)
```

## Generators → `Iterator` (preferred over `LazyList`)

When a Python method `yield`s items one at a time, the Scala equivalent is an
`Iterator`, produced cheaply from `IterableOnce`. Returning `List` eagerly
loses the laziness Python guaranteed; returning `LazyList` adds memoization
that can hold onto the whole stream.

```python
# Python
def process_batch(self, values):
    for v in values:
        yield self.process(v)
```

```scala
// Scala - lazy, no memoisation
def processBatch(values: IterableOnce[A]): Iterator[B] =
  values.iterator.map(process)
```

Use `LazyList` only when you also need its persistence (e.g., an infinite
Fibonacci series computed once and re-read).

## Tail Recursion

```python
# Python - no tail call optimization
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

# Workaround: iterative
def factorial_iter(n):
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
```

```scala
// Scala - tail recursion with annotation
import scala.annotation.tailrec

def factorial(n: Int): BigInt = {
  @tailrec
  def loop(n: Int, acc: BigInt): BigInt = {
    if (n <= 1) acc
    else loop(n - 1, n * acc)
  }
  loop(n, 1)
}
```

## Fluent Builders: Preserve Call Shape and Error Channel

A Python fluent builder that `append`s to internal `list`s and raises
`ValueError` on failed validation does **not** translate to a monadic
builder that returns `Either[Error, Value]`. The public API shape of such a
Python class is usually:

- Each `.with_*` method returns a builder, and
- `.build()` returns a **callable** (`T => Output`), not the finished object
  directly. The returned callable **raises** on validation failure, it does
  not swallow the error into an `Either`.

Preserve those two shapes in Scala:

```scala
// Scala — mirrors the Python callable shape.
final class Builder[T] private (
    normalizers: List[String => String],
    validators:  List[T => Boolean],
    metadata:    Map[String, Any]
) {
  def withNormalizer(n: String => String): Builder[T] =
    new Builder[T](normalizers :+ n, validators, metadata)

  def withValidator(v: T => Boolean): Builder[T] =
    new Builder[T](normalizers, validators :+ v, metadata)

  def withMetadata(entries: (String, Any)*): Builder[T] =
    new Builder[T](normalizers, validators, metadata ++ entries)

  // Return a plain function so downstream code can still write
  //   val run = builder.build; run(value)
  def build: T => Output = { value =>
    validators.foreach { v =>
      // Python raised ValueError → Scala IllegalArgumentException.
      if (!v(value))
        throw new IllegalArgumentException(s"Validation failed for $value")
    }
    val initial    = String.valueOf(value)
    val normalized = normalizers.foldLeft(initial)((acc, n) => n(acc))
    Output(normalized, metadata)
  }
}

object Builder {
  def apply[T](): Builder[T] = new Builder[T](Nil, Nil, Map.empty)
}
```

Two subtleties:

- `build` is a `def` returning a *function*, not a method with extra
  parameter lists. Writing `def build(value: T): Output = ???` changes the
  public shape even though the body is identical.
- The Python API lets callers *mutate-chain* (`b.with_metadata(k=1)` returns
  the same builder, enabling further mutation). An immutable Scala builder is
  safer and compatible as long as `with*` returns a fresh builder — but do
  not freeze the whole chain into a case class with fixed arity, because that
  removes the ability to keep an ordered list of handlers.

## Implicit Conversions and Type Classes

```python
# Python - no direct equivalent
# Duck typing provides flexibility
```

```scala
// Scala - type classes via implicits (Scala 2) or given/using (Scala 3)

// Scala 3
trait Show[A]:
  def show(a: A): String

given Show[Int] with
  def show(a: Int): String = s"Int: $a"

def display[A](a: A)(using s: Show[A]): String = s.show(a)

// Scala 2
trait Show[A] {
  def show(a: A): String
}

implicit val intShow: Show[Int] = new Show[Int] {
  def show(a: Int): String = s"Int: $a"
}

def display[A](a: A)(implicit s: Show[A]): String = s.show(a)
```
