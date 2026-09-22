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
    s"${m("name")} is ${m("age")}"  // beware: Map.apply throws if missing
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
```

```scala
// Scala - Option
def findUser(userId: Int): Option[User] = db.get(userId)
```

### Translating Python runtime dispatch (duck typing + None)

Python often accepts many runtime types in one function (e.g., `def tokenize(value: Any)`) and explicitly handles `None`.
In Scala, you can keep behavior **without** making the whole codebase `Any`-typed:

- Provide **typed entry points** where possible (overloads or distinct methods).
- Provide **one runtime-dispatch entry point** only where the Python truly does so.
- If the Python accepts `None`, the Scala runtime entry point should either:
  - accept `Any` and treat `null` as “missing”, or
  - accept `Option[Any]` and handle `None`.

Prefer a small “boundary” method with `Any`/`null` handling, and keep internal logic typed.

## Generators → Iterators/LazyList

```python
# Python
def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b
```

```scala
// Scala - LazyList (was Stream in Scala 2.12)
def fibonacci: LazyList[BigInt] = {
  def loop(a: BigInt, b: BigInt): LazyList[BigInt] =
    a #:: loop(b, a + b)
  loop(0, 1)
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
```

```scala
// Scala - Try monad
import scala.util.{Try, Success, Failure}

def parseInt(s: String): Try[Int] = Try(s.toInt)
```

## Function Composition

```python
# Python
def compose(f, g):
    return lambda x: f(g(x))
```

```scala
val addOne: Int => Int = _ + 1
val double: Int => Int = _ * 2

val composed = addOne.compose(double)  // addOne(double(x))
val pipeline = addOne.andThen(double).andThen(addOne)
```

## Currying and Partial Application

```python
# Python
from functools import partial

def add(a, b, c):
    return a + b + c
```

```scala
// Scala - curried functions
def add(a: Int)(b: Int)(c: Int): Int = a + b + c
```

## Tail Recursion

```python
# Python - no tail call optimization
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
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

### `@tailrec` safety rule (Scala 2.13)

Only annotate with `@tailrec` when the recursive call is syntactically in **tail position**.
A common non-tail pattern is mixing recursion with `Option.map/flatMap` or other higher-order calls:

```scala
// NOT tail-recursive (recursive call occurs inside flatMap)
// @tailrec  // would fail compilation
final def loop(parts: List[String], cur: Node): Option[Node] = parts match {
  case Nil => Some(cur)
  case p :: ps => cur.child(p).flatMap(loop(ps, _))
}
```

Fix by either:
- removing `@tailrec`, or
- rewriting to an explicit loop/fold that is actually tail-recursive.

## Implicit Conversions and Type Classes

```scala
// Scala 2 - type classes via implicits
trait Show[A] { def show(a: A): String }

implicit val intShow: Show[Int] = new Show[Int] {
  def show(a: Int): String = s"Int: $a"
}

def display[A](a: A)(implicit s: Show[A]): String = s.show(a)
```
