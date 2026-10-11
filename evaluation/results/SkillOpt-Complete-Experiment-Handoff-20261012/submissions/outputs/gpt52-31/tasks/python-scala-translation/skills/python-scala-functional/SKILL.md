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
  case List(x, y) => s"pair: $x, $y"      // Python [x, y]
  case (x, y) => s"tuple: $x, $y"          // Scala Tuple2
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



### Option vs Either vs Try (what to use when translating Python)

- Use **`Option[A]`** when the only information is *presence/absence* (Python `None`, missing key, optional field) and you do **not** need an error message.
  - Example: optional metadata, missing address, unmatched regex.
- Use **`Either[E, A]`** when failure is expected and you want to preserve *why* it failed (error string or a domain error ADT).
  - Example: numeric/temporal token rejected with a reason; validation errors.
- Use **`Try[A]`** when calling an API that throws (common during parsing) and you want to safely capture exceptions.
  - Convert to `Option`/`Either` at the boundary of your tokenizer logic.

Conversions:

```scala
import scala.util.{Try, Success, Failure}

val t: Try[Int] = Try("12".toInt)
val o: Option[Int] = t.toOption
val e: Either[Throwable, Int] = t.toEither

// Prefer mapping to domain errors instead of leaking Throwable
sealed trait TokenizeError
object TokenizeError {
  final case class NotANumber(input: String) extends TokenizeError
  final case class InvalidDate(input: String) extends TokenizeError
}

def asDomain[A](t: Try[A], onFail: Throwable => TokenizeError): Either[TokenizeError, A] =
  t.toEither.left.map(onFail)
```

### Safe parsing helpers (avoid exceptions/null in tokenizers)

```scala
import scala.util.Try
import java.time.{LocalDate, LocalDateTime, Instant}
import java.time.format.DateTimeFormatter

object SafeParse {
  def int(s: String): Option[Int] = Try(s.trim.toInt).toOption
  def long(s: String): Option[Long] = Try(s.trim.toLong).toOption
  def bigDecimal(s: String): Option[BigDecimal] = Try(BigDecimal(s.trim)).toOption

  def localDate(s: String, fmt: DateTimeFormatter): Option[LocalDate] =
    Try(LocalDate.parse(s.trim, fmt)).toOption

  def localDateTimeIso(s: String): Option[LocalDateTime] =
    Try(LocalDateTime.parse(s.trim)).toOption

  def instantIso(s: String): Option[Instant] =
    Try(Instant.parse(s.trim)).toOption
}

// When you need reasons (Either)
sealed trait ParseError
object ParseError {
  final case class NotInt(input: String) extends ParseError
  final case class NotPositive(input: String) extends ParseError
}

def parsePositiveInt(s: String): Either[ParseError, Int] =
  Try(s.trim.toInt).toEither
    .left.map(_ => ParseError.NotInt(s))
    .flatMap(n => if (n > 0) Right(n) else Left(ParseError.NotPositive(s)))
```

### Composing Option/Either/Try pipelines (token-stream friendly)

- **`map`** transforms inside the container.
- **`flatMap`** sequences dependent steps.
- **`collect`** filters + maps in one pass (useful for keeping only certain tokens).

```scala
// Example: split -> trim -> keep non-empty -> parse ints (dropping failures)
val ints: Seq[Int] =
  input.split(",").toSeq
    .map(_.trim)
    .filter(_.nonEmpty)
    .flatMap(s => SafeParse.int(s))   // Option -> 0/1 element via flatMap

// Example: keep only numeric tokens (collect)
sealed trait TokenType
object TokenType {
  case object Numeric extends TokenType
  case object String extends TokenType
}
final case class Token(text: String, tokenType: TokenType)

val numericTexts: Seq[String] =
  tokens.collect { case Token(t, TokenType.Numeric) => t }
```

Sequencing many parses:

```scala
// Option sequencing: fail-fast to None if any element fails
val maybeAll: Option[Seq[Int]] =
  inputParts.foldLeft(Option(Vector.empty[Int])) { (acc, s) =>
    for {
      xs <- acc
      n  <- SafeParse.int(s)
    } yield xs :+ n
  }

// Either sequencing: fail-fast with first error
val eitherAll: Either[ParseError, Vector[Int]] =
  inputParts.foldLeft(Right(Vector.empty[Int]): Either[ParseError, Vector[Int]]) { (acc, s) =>
    for {
      xs <- acc
      n  <- parsePositiveInt(s)
    } yield xs :+ n
  }
```
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



### Token streams: generator/iterator translation patterns

Python tokenizers commonly yield tokens lazily. In Scala 2.13:

- Use **`Iterator[Token]`** when you want single-pass, low-memory streaming.
- Use **`LazyList[Token]`** when you want a persistent lazy structure (can be memoized; be careful with memory for massive data).

```python
# Python: generator producing tokens
def tokens(text):
    for part in text.split():
        if part:
            yield part
```

```scala
// Scala: Iterator pipeline (streaming)
def tokens(text: String): Iterator[String] =
  text.split("\\s+").iterator
    .map(_.trim)
    .filter(_.nonEmpty)

// If API requires Seq, materialize explicitly
val materialized: Seq[String] = tokens(text).toVector
```

Pattern: yielding optional tokens

```scala
// If a step may or may not emit a token, return Option[Token] and flatten
val out: Iterator[Token] =
  parts.iterator
    .map(toTokenOpt)      // String => Option[Token]
    .flatMap(_.iterator)  // Option -> 0/1 element
```
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



### Translating Python exceptions to Try/Either at boundaries

Python tokenizers often do:
- `try/except` around parsing (int/float/date)
- return `None`/default on failure
- sometimes attach error metadata

Scala guideline:
- Use `Try(...)` to capture thrown exceptions from JDK/Scala parsing.
- Convert to `Option` when you want to *drop* failures.
- Convert to `Either[DomainError, A]` when you want to *explain* failures.

```scala
import scala.util.Try

// Default-on-failure (Python: except -> 0)
def parseIntOrZero(s: String): Int = Try(s.toInt).getOrElse(0)

// Drop-on-failure (Python: Optional[int])
def parseIntOpt(s: String): Option[Int] = Try(s.toInt).toOption

// Explain-on-failure (recommended for debugging/token metadata)
final case class BadNumber(input: String, message: String)

def parseIntEither(s: String): Either[BadNumber, Int] =
  Try(s.toInt).toEither.left.map(e => BadNumber(s, e.getMessage))
```
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
