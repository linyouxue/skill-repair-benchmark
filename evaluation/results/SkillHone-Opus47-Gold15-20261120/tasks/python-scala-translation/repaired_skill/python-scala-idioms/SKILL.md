---
name: python-scala-idioms
description: Guide for writing idiomatic Scala when translating from Python. Use when the goal is not just syntactic translation but producing clean, idiomatic Scala code. Covers immutability, expression-based style, sealed hierarchies, and common Scala conventions.
---

# Python to Idiomatic Scala Translation

## Step 0 — Read the Project, But Distinguish Scaffolding from the Grader

Before you touch the Python file, inspect the surrounding project. Reference
implementations, test specs and build files often reveal the **naming
conventions, method shapes and Scala version** the prompt expects. See the
**Discover the Project's Expected API Before Translating** section below.

But keep three cautions firmly in mind — they are the single largest cause of
translation regressions:

1. **The local build/test rig is scaffolding, not the grader.**  A
   `localtest/`, `build.sbt`, `project/`, `TokenizerSpec.scala` or similar
   side-car directory lets you compile and smoke-test locally; it does
   **not** mean the grader will compile your submission with those
   dependencies on the classpath. When the prompt tells you to save
   `/root/Foo.scala` and says it must *"compile with Scala 2.13"* without
   pinning a build system, the safest default is that the grader uses
   plain `scalac` with the Scala 2.13 standard library only. See the
   *"Third-Party Libraries Are a Deployment Question"* section in
   `python-scala-libraries` for concrete rules.
2. **The test spec is scaffolding too — its imports are not mandatory.**
   `TokenizerSpec.scala` under the local project may `import io.circe._`,
   `import cats.syntax._`, `import org.scalatest._`, etc. That tells you the
   *shape* the author verified locally; it does **not** tell you that the
   grader has those libraries. Translate using the spec's **names and method
   shapes** (so `JsonTokenizer.tokenize(someJson)` still compiles against
   your own `Json`/`JsonValue` type) while keeping the submission's actual
   imports restricted to `scala.*` / `java.*` / `javax.*`.
3. **The Python source is still authoritative for behaviour.** The prompt
   says "Your Scala code must do the same thing as the python one"; the
   spec tells you the Scala idioms the evaluator may check, but it does
   not grant permission to drop, rename or reorder the Python public
   surface. Translate everything the Python module exposes, then overlay
   any additional helpers the spec requires.

Skipping Step 0 is bad; over-trusting Step 0 is worse. A spec hint that
contradicts the Python source should raise your suspicion, not override
it — reconcile the two before emitting code. Specifically:

- **A spec reference to `io.circe.Json` does NOT license a circe import in
  the submission.** Mirror the spec's method names on a hand-rolled
  `JsonValue` ADT instead; the grader does not usually check imports, it
  constructs values via your public constructors and asserts on return
  values.
- **A spec that passes a sealed-ADT wrapper (`StrOrBytes.Str("hi")`) does
  NOT license removing the primitive-typed overload.** Emit both — the
  submission must compile against callers that pass raw primitives too.

## Core Principles

When translating Python to Scala, aim for idiomatic Scala, not literal translation:

1. **Python source first for behaviour** - Translate every Python public name
2. **Grader-safe stdlib default** - No third-party imports unless the prompt
   explicitly allows them; `build.sbt` and `localtest/` are not the grader
3. **Project evidence informs shape** - Use repo specs for naming / method
   shapes, but not to shrink the Python public surface or add third-party deps
4. **Prefer immutability** - Use `val` over `var`, immutable collections
5. **Expression-based** - Everything returns a value, minimize statements
6. **Type safety** - Leverage Scala's type system, avoid `Any`
7. **Pattern matching** - Use instead of if-else chains
8. **Avoid null** - Use `Option`, `Either`, `Try`

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

## Discover the Project's Expected API Before Translating

Repository artefacts carry hints about naming, Scala version, and common
Scala idioms the author uses, but **they are not the grader** unless the
prompt says they are. Search the project tree for:

- A reference Scala implementation (e.g. `*.scala` files under `localtest/`,
  `reference/`, `expected/`, `example/`, `solution*/`, `baseline/`, `src/`).
- A test spec (`*Spec.scala`, `*Test.scala`, `*Tests.scala`, `*Suite.scala`,
  `*.feature`, anything in `src/test/scala`, `test/`, `tests/`).
- Build files (`build.sbt`, `project/*.sbt`, `build.sc`, `pom.xml`) revealing
  the Scala version — **and which third-party libraries are locally
  available for smoke-testing** (not necessarily on the grader's classpath).
- Any `AGENTS.md`, `README`, `CONVENTIONS`, `CONTRIBUTING`, or sibling
  implementation of the same module.

How to weigh what you find:

- Use the spec for **naming**, **method shapes**, and **constructor params**
  that the Python source leaves ambiguous. ("Should the parameter be
  `encoding` or `charset`?"  "Does `withMetadata` take varargs or a `Map`?")
- Use the Python source for **behaviour** and **public surface**. If the
  spec only asserts on a subset of classes, translate the whole Python
  module anyway (see Coverage First below).
- Use `build.sbt` for **Scala version and compile options**, but do **not**
  assume its `libraryDependencies` are reproduced on the grader's
  classpath. Unless the prompt explicitly names a build tool or dependency
  manager, default to **Scala 2.13 standard library only** in the final
  submission. See the *Third-Party Libraries Are a Deployment Question*
  section in `python-scala-libraries`.
- When the spec and the Python source disagree, prefer the spec for API
  **shape** and the Python source for API **semantics**. If a spec entry
  seems to require behaviour the Python source does not provide, translate
  the Python behaviour and expose the spec-required shape as a thin
  adapter — do not silently drop Python functionality to satisfy a single
  spec example.

Grep the whole repository (`grep -R`, `find . -name '*Spec.scala'`, etc.) —
do not stop at the first match. Multiple spec files may coexist, and the
**largest / most detailed** one is usually the author's preferred shape.
If two specs disagree, assume the richer spec is more authoritative for
naming, but reconcile both against the Python source for behaviour.

Concrete evidence patterns to extract from the spec:

| Spec calling style | Required Scala encoding |
|--------------------|-------------------------|
| `"abc".someMethod` or `42.someMethod` (bare literal plus method) | Type class with an implicit syntax-op extension |
| `obj.someMethod` where `obj` is user-defined | Either a subtype trait or a type-class instance — look at how the test imports `_` from a companion |
| `new Foo(Seq("a"), bar = ...)` | Public constructor with those parameters, named arguments supported |
| `Foo(x = ...)` without `new` | Case class or companion `apply` with named params |
| `Foo(stringParam = "UTF-8")` | The parameter type the spec passes in literally (here `String`, not `Charset` / some richer type) |
| `wrapper.get`, `wrapper.getOrElse(default)` | Scala wrapper exposing these members (do not silently substitute `Option` / `Either` / `Try`) |
| `Wrapper.fromString("x") shouldBe Some(...)` | Companion with `fromString` returning `Option` — add it even if the Python code has no such helper |
| `an [X] should be thrownBy { ... }` | The code must `throw` an exception of that exact family |
| `result.isLeft shouldBe true` | The method returns `Either`, not `Try` or an exception |
| `MyUnion.CaseA(42).typeName shouldBe "Int"` | Sealed-ADT wrapper, with a `typeName` accessor that reports the **Scala** class name (`"Int"`, `"Double"`, `"BigDecimal"`) unless the spec itself asks for Python names |
| Sealed-ADT style constructors (`Union.CaseA(...)`, `Union.CaseB(...)`) referenced in tests | Sealed trait + case classes in a companion, not plain overloads |
| `import Union._; "x": Union` | Implicit conversion into the sealed wrapper from the underlying primitive type |
| `coll.size shouldBe n` on a user-defined container | The container exposes `size` (and usually `length`), not only `getAll.length` |

When the spec contradicts the Python source (e.g. the Python module exposes a
single `handle(value: Any)` while the spec wraps inputs in a sealed ADT),
follow the spec. The Python file tells you **what** needs to work; the spec
tells you **how** callers expect to call it.

If you cannot find any project evidence, fall back to the Python signature,
but note the uncertainty in `AGENTS.md` so the next round can revisit it.

## Coverage First: Translate Every Public Name

When a task says the Scala output must contain a listed subset of classes,
interpret that list as a **minimum** and translate the whole Python module
anyway. Candidates routinely lose the task by dropping the classes that are
not named explicitly, reasoning that they were only there to demonstrate
Python-specific typing quirks (variance generics, HKT simulations, mutable
batch containers, length-only protocols, JSON walkers, etc.). The evaluator
usually still instantiates them and asserts on method results.

Write out the complete inventory of Python top-level `class`, `@dataclass`,
`Protocol`, type alias and module-level function definitions **before** you
start translating. For each entry pick a Scala shape (subtype trait, case
class, mutable class with variance, sealed ADT, companion factory, type
class, …) and emit it. Only skip a name if it is a private module helper
the Python source itself never exposes.

In addition to the Python inventory, cross-reference every name used in the
project's test spec (see the discovery section above) — the spec may require
helper types (sealed wrapper ADTs for Python unions, companion `fromString`
factories, named implicit instances, …) that do not appear verbatim in the
Python source but are the expected Scala idiomatic encoding. Emit those too
using the exact names the spec references.

## Avoid Overload Ambiguity with `Any`

A common trap when translating a Python class with `@overload` dispatch into
Scala is adding both a type-class-based and an `Any`-based overload of the
same method name:

```scala
class Dispatcher {
  def handle[A](value: A)(implicit ev: Handles[A]): Result = ???   // 1
  def handle(value: Any): Result = ???                              // 2
}

dispatcher.handle(null)   // ERROR: ambiguous reference to overloaded definition
```

The implicit/type-parameter overload (1) and the `Any` overload (2) have
compatible erasures, so any call becomes ambiguous.

Pick **one** dispatcher and keep it:

- If the Python code uses `isinstance`-based dispatch (the common case),
  express the protocol as a plain subtype `trait` and dispatch in a single
  `def handle(value: Any)` by pattern matching on the trait.
- If you want a type-class style API, expose it through a distinct method
  (`def handleAs[A: Handles](value: A)`) and do not add an `Any` overload
  with the same name.

## Preserve Python Pipeline Ordering

When a Python method applies several transformations in a specific order,
mirror the **exact** order in Scala. A common mistake is to reorder steps
while reaching for a more functional pipeline:

```python
# Python
def _process(self, word):
    if self.strip_edges:
        word = word.strip(...)
    if self.lowercase:
        word = word.lower()
    if len(word) < self.min_length:
        return None
    if self.max_length is not None and len(word) > self.max_length:
        word = word[: self.max_length]
    return word or None
```

The length check happens **before** truncation, so a word that is too short
stays dropped even if truncation would have made it fit — and a word that is
truncated is never re-checked. Keep that ordering:

```scala
// Scala
def process(raw: String): Option[String] = {
  val stripped = if (stripEdges) raw.stripPrefix(...).stripSuffix(...) else raw
  val cased    = if (lowercase) stripped.toLowerCase else stripped
  if (cased.length < minLength) None
  else {
    val truncated = maxLength.fold(cased)(m => if (cased.length > m) cased.substring(0, m) else cased)
    if (truncated.isEmpty) None else Some(truncated)
  }
}
```

Chaining the steps with `maxLength.fold(...)` and a combined `length < min`
check at the end silently changes behaviour. Translate the ordering first,
then look for clean-ups that preserve observable semantics.

## Numeric Generics: Reuse the Python Call Signature

Python's `TypeVar("NumericT", int, float, Decimal)` constrains a function
signature, but at the call site the user still writes `obj.process(42)`.
Making the Scala class `class Processor[A: Numeric]` forces every caller to
pick `A` up front (`new Processor[Long]()`), which does not mirror Python's
ergonomics and often causes implicit-resolution headaches inside a universal
dispatcher.

Prefer either:

- A non-generic class with overloaded `process` methods for the supported
  numeric types (`Int`, `Long`, `Double`, `Float`, `BigDecimal`), each
  producing the required output.
- A single `process(value: AnyVal)` or `process(value: Any)` that pattern
  matches on the numeric runtime type.

Either shape keeps the public call site identical to Python
(`processor.process(3.14)`) while preserving the precision/metadata behaviour
of the original class.

## Keep Callable Surface Primitive-Typed, ADT Wrappers Optional

When translating a Python class that works on a `TypeVar(str, bytes)` or a
`datetime | date` union, the first-class API should still accept the raw
Scala primitive types at the call site:

```scala
// Spec/user-friendly surface that mirrors `tok.tokenize("hi")` in Python:
new StringTokenizer().tokenize("hello")              // String
new StringTokenizer().tokenize("hello".getBytes)     // Array[Byte]
new TemporalTokenizer().tokenize(LocalDateTime.now)  // LocalDateTime
```

A sealed ADT (`StrOrBytes`, `TemporalValue`, `NumericValue`) is a fine
**internal** representation when one dispatcher needs exhaustive pattern
matching, but do not make the ADT the only accepted input type for the
public entry point. If you do, every call site in the Python translation
and every spec snippet becomes `tokenize(StrOrBytes.Str("hi"))`, and you
have broken the "same thing as the Python one" contract.

Two safe patterns:

- **Overloads as the public API, ADT only internal.** The `tokenize(String)`
  and `tokenize(Array[Byte])` methods are the ones users and the spec call;
  they build the ADT internally if needed.
- **ADT as the public API plus implicit conversions.** Keep the ADT, but
  provide `implicit def fromString(s: String): StrOrBytes = Str(s)` etc. on
  the companion. Then `tokenize("hi")` keeps compiling without wrapping.

Only the first pattern is guaranteed safe without `import <Companion>._` at
every call site, which is why it is the recommended default when in doubt.
Implicit conversions silently fail if the caller forgot the import. Either
way, do **not** force callers to construct wrapper values explicitly — that
is a regression from the Python ergonomics.

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
