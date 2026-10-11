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



### Tokenizer Domain Modeling (Task-Aligned)

For this task, prefer explicit ADTs and immutable records instead of stringly-typed fields or mutable classes.

#### `TokenType` as a sealed ADT (Scala 2.13)

Model Python enums as a `sealed trait` with `case object`s so `match` is exhaustive.

```scala
sealed trait TokenType
object TokenType {
  case object String extends TokenType
  case object Numeric extends TokenType
  case object Temporal extends TokenType
  case object Universal extends TokenType
  case object Whitespace extends TokenType
}
```

#### `Token` as an immutable case class + copy-based metadata updates

Use a `case class` for `Token` and represent optional/extra attributes with an immutable map (or `Option` fields when the schema is fixed).

```scala
final case class Token(
  text: String,
  tokenType: TokenType,
  metadata: Map[String, String] = Map.empty
) {
  def withMetadata(key: String, value: String): Token =
    copy(metadata = metadata.updated(key, value))
}

object Token {
  // If tests require a function named `toToken`, keep it public and explicit.
  def toToken(text: String, tokenType: TokenType): Token = Token(text, tokenType)
}
```

#### Tokenizer APIs as traits/abstract classes with explicit return types

Use a shared base abstraction for common behavior and keep return types stable (`Seq[Token]`, `Vector[Token]`, or `List[Token]`).

```scala
trait BaseTokenizer {
  def tokenize(input: String): Seq[Token]

  def tokenizeBatch(inputs: Seq[String]): Seq[Seq[Token]] =
    inputs.map(tokenize)
}
```

#### Companion objects for factories/builders

Translate Python classmethods/utilities into companion object methods; keep required method names intact even if they are slightly un-Scala-like.

```scala
final class TokenizerBuilder(/* config */) {
  def build(): BaseTokenizer = ???
}

object TokenizerBuilder {
  def apply(/* config */): TokenizerBuilder = new TokenizerBuilder(/*...*/)
}
```

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



## Single-File Scala 2.13 Layout (Tokenizer.scala)

Scala 2.13 does not support arbitrary top-level functions. Put "module-level" functions (e.g., `tokenize`, `tokenizeBatch`, `toToken`, `withMetadata`) inside an `object`, while keeping classes/traits/case classes at the top level.

Recommended layout:

```scala
// Tokenizer.scala

// 1) ADTs / data types
sealed trait TokenType
final case class Token(/* ... */)

// 2) Tokenizers / builder types
trait BaseTokenizer { def tokenize(input: String): Seq[Token] }
final class StringTokenizer extends BaseTokenizer { /* ... */ }

// 3) Module-level functions required by tests
object TokenizerModule {
  def tokenize(input: String): Seq[Token] = ???
  def tokenizeBatch(inputs: Seq[String]): Seq[Seq[Token]] = ???
  def toToken(text: String, tokenType: TokenType): Token = ???
  def withMetadata(token: Token, key: String, value: String): Token = ???
}
```

If the test harness expects unqualified names, create a thin forwarder object with the expected name and delegate to your implementation.

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



### Translation Checklist (Python → idiomatic Scala for this task)

- Model closed sets like `TokenType` as `sealed trait` + `case object`s; rely on exhaustive `match`.
- Represent `Token` as a `case class`; update fields via `copy`, not mutation.
- Avoid `null`; use `Option` for absence and `Either`/`Try` for fallible parsing.
- Keep public API methods’ **names and arity** exactly as required by the task (`TokenType, Token, BaseTokenizer, ... tokenize, tokenizeBatch, toToken, withMetadata`).
- Add **explicit return types** on required public methods to prevent inference mismatches.
- Prefer immutable collections (`List`/`Vector`/`Seq`) for token streams; avoid shared mutable state.
- Use expression-based code and pattern matching rather than nested if/else.

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
