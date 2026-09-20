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



## End-to-End Tokenizer Architecture for Scala 2.13

For a Python tokenizer translation, first treat the source module as the behavioral contract. Inventory every public class, function, constructor/default, accepted input shape, output shape, fallback rule, and exception before choosing Scala abstractions. Preserve required externally visible names and observable behavior (`TokenType`, `Token`, `BaseTokenizer`, `StringTokenizer`, `NumericTokenizer`, `TemporalTokenizer`, `UniversalTokenizer`, `WhitespaceTokenizer`, `TokenizerBuilder`, `tokenize`, `tokenizeBatch`, `toToken`, and `withMetadata`) even when private implementation names follow normal Scala conventions. Do not change classification precedence, whitespace behavior, metadata contents, ordering, or failure behavior merely to make the design look more idiomatic.

### Immutable domain and configuration models

Represent source data with immutable `case class` values and `val` fields. Keep token fields, metadata, and configuration explicitly typed; use immutable `Map`, `List`, `Vector`, or another collection whose ordering and access behavior matches the Python code. Put defaults and validated construction in companion objects rather than mutable constructor state:

```scala
final case class TokenConfig(/* fields derived from the source contract */)

object TokenConfig {
  def default: TokenConfig = /* source-compatible defaults */
  def apply(/* public construction arguments */): TokenConfig = /* construct immutably */
}

final case class Token(/* source fields */, metadata: Map[String, String] = Map.empty)

object Token {
  def withMetadata(token: Token, metadata: Map[String, String]): Token =
    token.copy(metadata = token.metadata ++ metadata)
}
```

The examples are structural guidance: use the actual Python fields, metadata value types, merge direction, and default values rather than inventing new semantics. If `TokenType` is a closed set in the source, model it with a `sealed trait` and `case object`/`case class` members in its companion. Match on that hierarchy exhaustively and avoid `String`, `Any`, casts, or a catch-all case that silently hides an unsupported source variant.

### Separate policy from orchestration

Keep classification policy separate from the flow that traverses input. A useful shape is an immutable base abstraction whose concrete tokenizers implement one focused decision, while `UniversalTokenizer` or the public `tokenize` entry point owns ordering, delegation, token assembly, and fallback behavior. `StringTokenizer`, `NumericTokenizer`, `TemporalTokenizer`, and `WhitespaceTokenizer` should not share mutable accumulators or mutate configuration. `BaseTokenizer` can expose a narrow typed operation such as a classification attempt; the concrete policies should return a typed result that lets the orchestrator decide whether to continue.

Use an immutable builder whose methods return `this.copy(...)` (or a new builder) and whose `build` method creates the final tokenizer. Companion `apply`/factory methods are appropriate for defaults and source-compatible convenience construction. Keep required public classes and methods public; make helpers `private` or `private[package]` only when the Python API does not expose them. Use camelCase for newly introduced private Scala identifiers, but retain any required public spelling exactly.

The orchestration should be expression-oriented: use `foldLeft`, `map`, `flatMap`, `collect`, or a small recursive function instead of a mutable Python-style accumulator. Make dispatch precedence explicit in one place and use pattern matching for token types and policy results. If a match is intended to be exhaustive, let the compiler check it; do not use Scala 3 `enum`, `given`, extension methods, union types, or other syntax unavailable in Scala 2.13.

### Absence, recoverable failures, and compatibility

Choose the result type based on the source contract, not on a blanket rule:

- Use `Option[A]` when absence is expected and carries no diagnostic, such as “this policy does not recognize the value” or an optional metadata field. Prefer `None`/`Some` and combinators over `null` and sentinel strings.
- Use `Either[Error, A]` when callers can reasonably inspect or handle a parsing/validation failure. Define a small typed error model when the source distinguishes failure causes; preserve input context only when the source exposes or needs it.
- Use `Try[A]` when wrapping an existing Scala operation that may throw and the useful contract is success versus captured exception, especially at an integration boundary.
- Throw an exception only when the Python API raises for that condition, when an invalid configuration is a programmer error, or when required source compatibility means callers expect an exception. Do not catch broad exceptions and convert them to absence if that changes observable behavior.

Distinguish “not handled by this tokenizer” from “malformed input” so fallback remains faithful: the former is commonly `None`, while the latter may be an `Either`/`Try` failure or an exception according to the source. Public convenience functions should delegate to the same configured orchestration path as the classes, and `tokenizeBatch` should preserve input order, empty-input behavior, and per-item failure semantics. Do not introduce parallelism or mutable shared state merely because the eventual data is massive; make the core tokenizer referentially transparent so a caller can add distributed execution safely.

### Translation checklist

Before finalizing, verify that the Scala 2.13 source compiles with the target compiler and that it contains every required public declaration. Compare representative cases with the Python implementation, including empty and whitespace-only values, recognized and unrecognized strings, numeric and temporal boundaries, metadata updates, batch ordering, defaults, and each fallback/error path. Prefer readable explicit types at public boundaries, exhaustive matches, immutable values, and small policy classes over a literal line-by-line translation.
