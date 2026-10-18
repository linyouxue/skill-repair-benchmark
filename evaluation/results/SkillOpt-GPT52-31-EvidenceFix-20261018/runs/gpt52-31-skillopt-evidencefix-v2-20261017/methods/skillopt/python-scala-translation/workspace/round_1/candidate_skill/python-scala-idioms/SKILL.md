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



## Translation Templates: Tokenizers, Tokens, and Builders (Scala 2.13)

When translating a Python “tokenizer module” (multiple tokenizers + builder + free functions), prefer these Scala templates.

### 1) TokenType as a sealed ADT (not strings/ints)

**Python pattern:** stringly-typed token kinds (e.g., `"string"`, `"numeric"`).

**Scala template:**

```scala
sealed trait TokenType extends Product with Serializable
object TokenType {
  case object StringT extends TokenType
  case object NumericT extends TokenType
  case object TemporalT extends TokenType
  case object WhitespaceT extends TokenType
  case object UnknownT extends TokenType
}
```

Use `case object`s so pattern matches are exhaustive and cheap.

### 2) Token as an immutable case class + enrichment via copy

Prefer a single immutable data type and pure enrichment methods.

```scala
final case class Token(
  tokenType: TokenType,
  text: String,
  metadata: Map[String, String] = Map.empty
) {
  def withMetadata(kv: (String, String)*): Token = copy(metadata = metadata ++ kv)
}
```

### 3) BaseTokenizer as an interface with Option/Either

**Avoid:** returning `null` or throwing for control flow.

```scala
trait BaseTokenizer[-A] {
  def tokenize(value: A): Either[String, Token] // Left = validation/parse error

  def tokenizeBatch(values: Iterable[A]): Iterator[Either[String, Token]] =
    values.iterator.map(tokenize)
}
```

Use `Either` when callers must distinguish “invalid input” from success; use `Option` only when absence is non-informational.

### 4) Runtime dispatch via pattern matching (UniversalTokenizer)

For “universal” Python tokenizers that inspect runtime types, implement dispatch explicitly and keep it expression-oriented.

```scala
final class UniversalTokenizer(
  stringTok: BaseTokenizer[String],
  numericTok: BaseTokenizer[BigDecimal]
) extends BaseTokenizer[Any] {
  override def tokenize(value: Any): Either[String, Token] = value match {
    case null => Left("null value")
    case s: String => stringTok.tokenize(s)
    case i: Int => numericTok.tokenize(BigDecimal(i))
    case l: Long => numericTok.tokenize(BigDecimal(l))
    case bd: BigDecimal => numericTok.tokenize(bd)
    case other => Right(Token(TokenType.UnknownT, other.toString).withMetadata("originalType" -> other.getClass.getName))
  }
}
```

### 5) Immutable builder pattern (TokenizerBuilder)

When Python uses a mutable builder, translate to an immutable builder returning new instances.

```scala
final case class TokenizerBuilder[A](
  base: BaseTokenizer[A],
  enrich: Token => Token = identity,
  validate: A => Either[String, A] = Right(_)
) {
  def withMetadata(f: Token => Token): TokenizerBuilder[A] = copy(enrich = enrich.andThen(f))
  def withValidator(v: A => Either[String, A]): TokenizerBuilder[A] = copy(validate = validate.andThen(_.flatMap(v)))

  def build(): BaseTokenizer[A] = new BaseTokenizer[A] {
    override def tokenize(value: A): Either[String, Token] =
      validate(value).flatMap(base.tokenize).map(enrich)
  }
}
```

This preserves referential transparency and composes behaviors cleanly.

### 6) Keep module-level functions in an `object`

Python module-level functions (e.g., `tokenize`, `tokenizeBatch`, `toToken`, `withMetadata`) map naturally to Scala `object` utilities.

```scala
object TokenizerApi {
  def tokenize[A](tok: BaseTokenizer[A], a: A): Either[String, Token] = tok.tokenize(a)
  def tokenizeBatch[A](tok: BaseTokenizer[A], as: Iterable[A]): Iterator[Either[String, Token]] = tok.tokenizeBatch(as)

  def toToken(tpe: TokenType, text: String): Token = Token(tpe, text)
  def withMetadata(token: Token, kv: (String, String)*): Token = token.withMetadata(kv: _*)
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



## Validation & Error Flows: Prefer Either over Exceptions

Python tokenizers often raise exceptions (parse errors) or return sentinel values. In Scala, model this explicitly.

### Parse + enrich pipeline

```scala
def parseInt(s: String): Either[String, Int] =
  scala.util.Try(s.trim.toInt).toEither.left.map(_ => s"not an int: '$s'")

def tokenizeNumeric(s: String): Either[String, Token] =
  parseInt(s).map { n =>
    Token(TokenType.NumericT, n.toString).withMetadata("original" -> s)
  }
```

### Accumulating validation errors (when needed)

If the Python code collects multiple errors, consider returning `List[String]` on the left.

```scala
type ErrorsOr[A] = Either[List[String], A]

def requireNonEmpty(s: String, field: String): ErrorsOr[String] =
  if (s.nonEmpty) Right(s) else Left(List(s"$field is empty"))

def requireMaxLen(s: String, n: Int, field: String): ErrorsOr[String] =
  if (s.length <= n) Right(s) else Left(List(s"$field too long"))

def validate(s: String): ErrorsOr[String] =
  requireNonEmpty(s, "value").left.flatMap(es1 =>
    requireMaxLen(s, 32, "value").left.map(es2 => es1 ++ es2)
  )
```

Use exceptions only for truly exceptional conditions (I/O failures, programmer errors), not routine parse/validation outcomes.

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



## Tokenizer-Style Batch APIs: Iterators, Views, and Memory

Python implementations often build large lists eagerly. For massive/distributed data, prefer streaming-like APIs.

```scala
// Good default: Iterator to avoid allocating full results
def tokenizeBatch[A](tok: BaseTokenizer[A], as: Iterable[A]): Iterator[Either[String, Token]] =
  as.iterator.map(tok.tokenize)

// If you must materialize, make it explicit
val out: List[Either[String, Token]] = tokenizeBatch(tok, inputs).toList
```

Avoid mutable accumulators; use `iterator.map`, `foldLeft`, or `view` depending on needs.

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



### Tokenizer translation anti-patterns

```scala
// DON'T: stringly-typed token kinds
case class Token(kind: String, text: String)

// DO: sealed ADT
sealed trait TokenType
case object StringT extends TokenType
final case class Token(tokenType: TokenType, text: String)

// DON'T: mutable builder
final class Builder {
  var normalize: String => String = identity
  def withNormalize(f: String => String): Builder = { normalize = f; this }
}

// DO: immutable builder with copy
final case class Builder(normalize: String => String = identity) {
  def withNormalize(f: String => String): Builder = copy(normalize = f)
}

// DON'T: throw for parse failures
def parse(s: String): Int = s.toInt // may throw

// DO: Either/Try and handle at the boundary
def parse(s: String): Either[String, Int] = scala.util.Try(s.toInt).toEither.left.map(_.getMessage)
```

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
