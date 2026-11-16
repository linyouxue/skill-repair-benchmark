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



## Composable Option/Either Pipelines

```python
# Python - None + exceptions mixed together
from typing import Optional


def parse_port(raw: Optional[str]) -> int:
    if raw is None:
        return 8080

    try:
        port = int(raw)
    except ValueError:
        return 8080

    return port if 0 < port < 65536 else 8080
```

```scala
// Scala 2.13 - compose absence + validation explicitly
import scala.util.Try

def parsePort(raw: Option[String]): Int = {
  raw
    .flatMap(s => Try(s.toInt).toOption)
    .filter(p => p > 0 && p < 65536)
    .getOrElse(8080)
}

// Prefer Either when callers need error details

def validatePort(raw: String): Either[String, Int] =
  Try(raw.toInt).toEither
    .left.map(_ => s"Invalid integer: $raw")
    .flatMap { p =>
      Either.cond(p > 0 && p < 65536, p, s"Out of range: $p")
    }

// Scala 2.13 Either is right-biased:
// map/flatMap operate on the Right value
val normalized: Either[String, String] =
  validatePort("8080")
    .map(_.toString)
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



Tokenizer/data-pipeline style flows are usually cleaner when each stage returns
`Option`, `Either`, or `Try` instead of throwing exceptions.

```scala
case class Token(text: String, metadata: Map[String, String])

val normalize: String => String = _.trim.toLowerCase

def validateToken(text: String): Either[String, String] =
  Either.cond(text.nonEmpty, text, "Empty token")

// Metadata propagation through a pipeline

def toToken(raw: String, index: Int): Either[String, Token] =
  validateToken(normalize(raw))
    .map { clean =>
      Token(clean, Map("index" -> index.toString))
    }

// Runtime dispatch via pattern matching

def tokenize(value: Any): Either[String, Token] = value match {
  case s: String => toToken(s, 0)
  case n: Int => Right(Token(n.toString, Map("type" -> "numeric")))
  case null => Left("Cannot tokenize null")
  case other => Left(s"Unsupported value: ${other.getClass.getSimpleName}")
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



`@tailrec` only works when the recursive call is in tail position.
Common failure cases:

```scala
// NOT tail-recursive: work happens after recursion returns

def sum(xs: List[Int]): Int = xs match {
  case Nil => 0
  case head :: tail => head + sum(tail)
}
```

Prefer iterative collection operators for large data pipelines:

```scala
// Idiomatic replacements
val total = xs.foldLeft(0)(_ + _)

// Streaming batch processing
val cleaned =
  Iterator(" A ", "", "B")
    .map(_.trim)
    .filter(_.nonEmpty)
    .toList

// Stateful generation
val fibs = Iterator.unfold((0, 1)) {
  case (a, b) => Some((a, (b, a + b)))
}
```

For performance-sensitive tokenization loops over very large inputs, a local
`while` loop with mutable builders can be more idiomatic and memory-efficient
than deep recursion.

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



## Builder and Batch Processing Patterns

```scala
case class Token(text: String, metadata: Map[String, String] = Map.empty) {
  def withMetadata(entries: (String, String)*): Token =
    copy(metadata = metadata ++ entries)
}

trait BaseTokenizer {
  def tokenize(value: String): Either[String, Token]

  // Keep batch APIs lazy for distributed/large-scale processing
  def tokenizeBatch(values: Iterator[String]): Iterator[Either[String, Token]] =
    values.map(tokenize)
}

final case class WhitespaceTokenizer(lowercase: Boolean) extends BaseTokenizer {
  override def tokenize(value: String): Either[String, Token] = {
    val normalized = if (lowercase) value.toLowerCase else value

    Either.cond(
      normalized.trim.nonEmpty,
      Token(normalized).withMetadata("tokenizer" -> "whitespace"),
      "Input was empty"
    )
  }
}

// Builder pattern is preferred over many overloaded constructors
final class TokenizerBuilder {
  private var lowercase = false

  def withLowercase(enabled: Boolean): TokenizerBuilder = {
    lowercase = enabled
    this
  }

  def build(): BaseTokenizer =
    WhitespaceTokenizer(lowercase)
}
```
