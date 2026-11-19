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

## Translation Workflow (Completeness + Scala 2.13 constraints)

For non-trivial modules, prioritize **API completeness** and **Scala 2.13 compatibility** before micro-optimizing style.

1. **Inventory the Python surface area**
   - List every top-level `class` / `def` / `Enum` and any public constants or type aliases that are used across the module.
   - Treat the task’s “required identifiers” list as **illustrative** unless it explicitly says it is exhaustive.

2. **Create a Scala skeleton first**
   - In Scala 2.13, put “top-level functions” inside an `object` (Scala 2 has no top-level `def`).
   - Add all required names (types, methods, and companion `object`s) as stubs so you can compile early.

3. **Preserve the required public API**
   - Keep exact identifier names when the prompt/tests reference them (e.g., enum-like members such as `TokenType.STRING`).
   - You can still be idiomatic internally: keep implementation details private, prefer immutability, and expose a small, clear API.

4. **Use types deliberately**
   - Prefer specific types (`String`, `Int`, `BigDecimal`, `LocalDateTime`, etc.) and `Option`/`Either` for absence/errors.
   - Use `Any` only at dynamic boundaries (e.g., “universal” dispatch), and immediately narrow with pattern matching.

5. **Validate with small checks**
   - Ensure the file compiles with Scala 2.13.
   - Add a couple of tiny sanity checks (or a minimal `main`) only if the task allows it; otherwise keep code library-like.

### Tool-call hygiene (prevents avoidable run failures)

In tool-driven environments (where file views / terminal commands are invoked via a **structured** tool call), formatting mistakes can stop the run before you ever reach the coding step.

Rules of thumb:

- **Tool calls must be machine-readable only**: emit exactly **one** tool call payload with **no surrounding prose**, no Markdown fences, and no trailing characters.
  - Good: `{"command":"view","path":"...","view_range":[1,200]}`
  - Bad: `I'll view it: {"command":"view","path":"..."}` (extra text can break parsing)
- **Keep the payload strictly valid** (balanced braces/brackets, double quotes for keys/strings, no trailing commas).
- **One tool call per message**: if you need multiple views/commands, do them as separate calls (or combine shell commands with `&&` *inside* a single terminal call if allowed).
- **Handle truncation intentionally**: if a view is truncated, request the next chunk (e.g., advance `view_range`) rather than guessing missing definitions.
- **Recover fast from malformed calls**: resend the corrected payload immediately; do not “explain” the correction in the same message as the tool call.

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

// Or use a small helper for debugging (Scala 2.13-friendly)
implicit class TapOps[A](private val a: A) extends AnyVal {
  def tap(f: A => Unit): A = { f(a); a }
}

val items = (0 until 10)
  .map(_ * 2)
  .tap(xs => xs.foreach(x => println(s"Value: $x")))
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
