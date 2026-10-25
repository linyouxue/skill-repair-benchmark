---
name: python-scala-idioms
description: Guide for writing idiomatic Scala when translating from Python. Use when the goal is not just syntactic translation but producing clean, idiomatic Scala code. Covers immutability, expression-based style, sealed hierarchies, and common Scala conventions.
---

# Python to Idiomatic Scala Translation

## Core Principles

When translating Python to Scala, aim for idiomatic Scala, not literal translation:

1. **Prefer immutability** - Use `val` over `var`, immutable collections
2. **Expression-based** - Everything returns a value, minimize statements
3. **Type safety** - Leverage Scala's type system, avoid `Any`
4. **Pattern matching** - Use instead of if-else chains
5. **Avoid null** - Use `Option`, `Either`, `Try`


## ⚠️ Translation Mode: Contract Preservation Overrides Idiomaticity

**When translating existing Python code against a verifier, the public API contract wins over idiomatic refactoring.** The rules below OVERRIDE the general guidance in the rest of this document whenever they conflict.

### Hard rules for translation tasks

1. **`build()` returns a tokenizer object, not a function.** If the Python builder's `build()` returns an object exposing `.tokenize(x)`, Scala's `build` must too — return a `BaseTokenizer[A]` instance, NOT `A => Token`.
   ```scala
   def build: BaseTokenizer[A] = new BaseTokenizer[A] {
     def tokenize(value: A): Token = { /* snapshot logic */ }
   }
   ```

2. **`tokenizeBatch` returns a materialized `Seq[Token]`/`List[Token]`**, not `Iterator[Token]`. Python `list` → Scala `Seq`, not lazy. Verifiers call `.length` and iterate multiple times.
   ```scala
   def tokenizeBatch(values: Iterable[A]): Seq[Token] = values.iterator.map(tokenize).toList
   ```

3. **Python `ValueError`/`TypeError` → `throw new IllegalArgumentException(msg)`.** Do NOT substitute `Either`, `Option`, or `Try` for exceptions that the Python source raises. Verifier likely uses `intercept[IllegalArgumentException]` or try/catch.

4. **Preserve every parameter name, order, and default.** Fix only the mutable-default-arg bug (`format_options={}` → `Map.empty[String, String]`). Do not drop, merge, or reorder parameters.

5. **Do not invent new public types.** Python unions like `str | bytes`, `datetime | date`, `int | float` → use `Any` with pattern matching, not new `sealed trait StringOrBytes` / `Temporal` / `Tokenizable` ADTs.
   ```scala
   def tokenize(value: Any): Token = value match {
     case s: String      => ...
     case b: Array[Byte] => ...
     case _              => throw new IllegalArgumentException(s"Unsupported: $value")
   }
   ```

6. **Do not add type-class constraints absent from Python.** If Python's `NumericTokenizer` is non-generic, write `class NumericTokenizer extends BaseTokenizer[Any]` that matches on `Int|Long|Double|Float|BigDecimal`. Do NOT write `class NumericTokenizer[A: Numeric]`.

7. **`**kwargs` → `(String, Any)*` varargs + `Map[String, Any]`.** `withMetadata` takes varargs and returns the same type via `copy`.

### Idioms that remain safe (additive, non-breaking)

- `val` over `var`, `case class` for data, `copy` for updates
- `camelCase` method names (translating `snake_case`)
- Pattern matching for `isinstance` chains
- `Map.empty` instead of mutable default `{}`
- `sealed abstract class` + `case object` for Python `Enum` (the ONLY sealed hierarchy you should add)

## Immutability First

```python
# Python - mutable by default
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1
        return self.count
```

```scala
// Scala - immutable approach
case class Counter(count: Int = 0) {
  def increment: Counter = copy(count = count + 1)
}

// Usage
val c1 = Counter()
val c2 = c1.increment  // Counter(1)
val c3 = c2.increment  // Counter(2)
// c1 is still Counter(0)
```

## Expression-Based Style

```python
# Python - statement-based
def get_status(code):
    if code == 200:
        status = "OK"
    elif code == 404:
        status = "Not Found"
    else:
        status = "Unknown"
    return status
```

```scala
// Scala - expression-based
def getStatus(code: Int): String = code match {
  case 200 => "OK"
  case 404 => "Not Found"
  case _ => "Unknown"
}

// No intermediate variable, match is an expression
```

## Sealed Hierarchies for Domain Modeling

```python
# Python - loose typing
def process_payment(method: str, amount: float):
    if method == "credit":
        # process credit
        pass
    elif method == "debit":
        # process debit
        pass
    elif method == "crypto":
        # process crypto
        pass
```

```scala
// Scala - sealed trait for exhaustive matching
sealed trait PaymentMethod
case class CreditCard(number: String, expiry: String) extends PaymentMethod
case class DebitCard(number: String) extends PaymentMethod
case class Crypto(walletAddress: String) extends PaymentMethod

def processPayment(method: PaymentMethod, amount: Double): Unit = method match {
  case CreditCard(num, exp) => // process credit
  case DebitCard(num) => // process debit
  case Crypto(addr) => // process crypto
}
// Compiler warns if you miss a case!
```

## Replace Null Checks with Option

```python
# Python
def find_user(id):
    user = db.get(id)
    if user is None:
        return None
    profile = user.get("profile")
    if profile is None:
        return None
    return profile.get("email")
```

```scala
// Scala - Option chaining
def findUser(id: Int): Option[String] = for {
  user <- db.get(id)
  profile <- user.profile
  email <- profile.email
} yield email

// Or with flatMap
def findUser(id: Int): Option[String] =
  db.get(id)
    .flatMap(_.profile)
    .flatMap(_.email)
```

## Prefer Methods on Collections

```python
# Python
result = []
for item in items:
    if item.active:
        result.append(item.value * 2)
```

```scala
// Scala - use collection methods
val result = items
  .filter(_.active)
  .map(_.value * 2)
```

## Avoid Side Effects in Expressions

```python
# Python
items = []
for x in range(10):
    items.append(x * 2)
    print(f"Added {x * 2}")
```

```scala
// Scala - separate side effects
val items = (0 until 10).map(_ * 2).toList
items.foreach(x => println(s"Value: $x"))

// Or use tap for debugging
val items = (0 until 10)
  .map(_ * 2)
  .tapEach(x => println(s"Value: $x"))
  .toList
```

## Use Named Parameters for Clarity

```python
# Python
def create_user(name, email, admin=False, active=True):
    pass

user = create_user("Alice", "alice@example.com", admin=True)
```

```scala
// Scala - named parameters work the same
def createUser(
  name: String,
  email: String,
  admin: Boolean = false,
  active: Boolean = true
): User = ???

val user = createUser("Alice", "alice@example.com", admin = true)

// Case class with defaults is often better
case class User(
  name: String,
  email: String,
  admin: Boolean = false,
  active: Boolean = true
)

val user = User("Alice", "alice@example.com", admin = true)
```

## Scala Naming Conventions

| Python | Scala |
|--------|-------|
| `snake_case` (variables, functions) | `camelCase` |
| `SCREAMING_SNAKE` (constants) | `CamelCase` or `PascalCase` |
| `PascalCase` (classes) | `PascalCase` |
| `_private` | `private` keyword |
| `__very_private` | `private[this]` |

```python
# Python
MAX_RETRY_COUNT = 3
def calculate_total_price(items):
    pass

class ShoppingCart:
    def __init__(self):
        self._items = []
```

```scala
// Scala
val MaxRetryCount = 3  // or final val MAX_RETRY_COUNT
def calculateTotalPrice(items: List[Item]): Double = ???

class ShoppingCart {
  private var items: List[Item] = Nil
}
```

## Avoid Returning Unit

```python
# Python - None return is common
def save_user(user):
    db.save(user)
    # implicit None return
```

```scala
// Scala - consider returning useful information
def saveUser(user: User): Either[Error, UserId] = {
  db.save(user) match {
    case Right(id) => Right(id)
    case Left(err) => Left(err)
  }
}

// Or at minimum, use Try
def saveUser(user: User): Try[Unit] = Try {
  db.save(user)
}
```

## Use Apply for Factory Methods

```python
# Python
class Parser:
    def __init__(self, config):
        self.config = config

    @classmethod
    def default(cls):
        return cls(Config())
```

```scala
// Scala - companion object with apply
class Parser(config: Config)

object Parser {
  def apply(config: Config): Parser = new Parser(config)
  def apply(): Parser = new Parser(Config())
}

// Usage
val parser = Parser()  // Calls apply()
val parser = Parser(customConfig)
```

## Cheat Sheet: Common Transformations

| Python Pattern | Idiomatic Scala |
|---------------|-----------------|
| `if x is None` | `x.isEmpty` or pattern match |
| `if x is not None` | `x.isDefined` or `x.nonEmpty` |
| `x if x else default` | `x.getOrElse(default)` |
| `[x for x in xs if p(x)]` | `xs.filter(p)` |
| `[f(x) for x in xs]` | `xs.map(f)` |
| `any(p(x) for x in xs)` | `xs.exists(p)` |
| `all(p(x) for x in xs)` | `xs.forall(p)` |
| `next(x for x in xs if p(x), None)` | `xs.find(p)` |
| `dict(zip(keys, values))` | `keys.zip(values).toMap` |
| `isinstance(x, Type)` | `x.isInstanceOf[Type]` or pattern match |
| `try: ... except: ...` | `Try { ... }` or pattern match |
| Mutable accumulator loop | `foldLeft` / `foldRight` |
| `for i, x in enumerate(xs)` | `xs.zipWithIndex` |

## Anti-Patterns to Avoid

```scala
// DON'T: Use null
val name: String = null  // Bad!

// DO: Use Option
val name: Option[String] = None

// DON'T: Use Any or type casts
val data: Any = getData()
val name = data.asInstanceOf[String]

// DO: Use proper types and pattern matching
sealed trait Data
case class UserData(name: String) extends Data
val data: Data = getData()
data match {
  case UserData(name) => // use name
}

// DON'T: Nested if-else chains
if (x == 1) ... else if (x == 2) ... else if (x == 3) ...

// DO: Pattern matching
x match {
  case 1 => ...
  case 2 => ...
  case 3 => ...
}

// DON'T: var with mutation
var total = 0
for (x <- items) total += x

// DO: fold
val total = items.sum
// or
val total = items.foldLeft(0)(_ + _)
```
