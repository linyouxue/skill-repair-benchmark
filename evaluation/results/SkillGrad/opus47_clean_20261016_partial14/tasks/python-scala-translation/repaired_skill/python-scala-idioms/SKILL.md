---
name: python-scala-idioms
description: Guide for writing idiomatic Scala when translating from Python. Teaches the API-shape ↔ idiomatic axis — how to read the task statement to pick which pole applies — plus the operation rules for each pole.
---

# Python to Idiomatic Scala Translation

## Pick the API-shape ↔ idiomatic axis from the task statement

Translation tasks live on an axis with two poles that pull in opposite
directions. Pick BEFORE writing Scala — neither pole is correct by default.

- **Pole (a) — Preserve the Python public API shape.** The evaluator calls
  the Scala using Python names, Python-accepted argument types, and expects
  Python return types verbatim. It also **reads string values back out of
  maps and enums using the Python spellings**. Use overloads or `Any`+match
  for unions, keep `snake_case` on keyword constructor params, do not wrap
  return values in `Try`/`Either`, do not force wrapper ADTs on callers,
  keep Python enum member names verbatim (`STRING` stays `STRING`), keep
  string-literal metadata keys and type tags verbatim (`"original_type"`
  stays `"original_type"`), do not add methods or metadata keys not in
  the Python source.
- **Pole (b) — Idiomatic Scala for a "proficient Scala developer".** The
  grader penalizes word-to-word translations. Use bounded generics / sealed
  ADTs / type classes for TypeVars, `Try`/`Either` for errors, persistent
  immutable builders, `UpperCamelCase` enum members, locale-safe formatting.

| Grep the task for … | Pole |
|---|---|
| "same classes/functions as the Python source", "must have all classes and functions in the python code", "do the same thing", named public APIs (methods/classes) listed verbatim, "preserve the Python public API", "same signatures", an evaluator snippet with raw Python types, `snake_case` kwargs | **(a)** |
| "proficient Scala developer", "idiomatic Scala", "should not be a word-to-word translation", "proper abstractions for representing data", "handle errors naturally in Scala", "use the Scala type system", "immutable" | **(b)** |
| Both sets of phrases present | **mixed** — pole (a) at the public boundary, pole (b) in internals |

### Required artifact — write before any Scala

Write these four lines at the top of your plan. If any line is empty,
re-read the task statement before continuing:

```
Named public APIs (verbatim from the task): <list>
Signal phrase (verbatim quote from the task): "<quote>"
Chosen pole: (a) | (b) | mixed
Raw-type evaluator call sites (derived from the named APIs, using ONLY
Python-shaped types — no wrapper ADTs, no `.get` on `Try`, no `.right.get`
on `Either`, no translator-defined helpers):
  <2-3 call sites, e.g. `new StringTokenizer().tokenize("hello"): Token`,
   `TokenType.STRING: TokenType`, `token.withMetadata(Map("k" -> v)): Token`>
```

The ambient tone of these skill files leads toward pole (b) ("idiomatic
Scala", "proficient developer"). If the task names public APIs verbatim
AND asks to "do the same thing" / "same classes/functions" / "must have
all classes and functions", that is a pole-(a) signal that **overrides
the ambient tone**. The axis is not pinned by what feels Scala-idiomatic;
it is pinned by signal phrases.

If signals are absent either way: default to pole (a) when the task shows
an evaluator call site with raw Python types or lists public API names;
otherwise default to pole (b).

Read `references/task-statement-axis-calibration.md` for the required-
artifact template, the full signal-phrase list, the mixed-case tactic,
and worked pole-(a) / pole-(b) decision examples. Skip when the four
required-artifact lines above are all filled and the pole is unambiguous.

## Translation workflow (do this before writing any Scala)

0. **Pre-flight gate.** Confirm your plan contains all four of the
   required-artifact lines above (Named APIs, Signal phrase, Chosen pole,
   Raw-type call sites) BEFORE moving to step 1. If `Chosen pole:` is
   absent or any raw-type call site uses a translator-defined wrapper
   (`StrOrBytes.Str(...)`, `.get` on `Try`, `.right.get` on `Either`),
   STOP — re-read `references/task-statement-axis-calibration.md` and
   fill the artifact. Do not emit Scala while the gate is open.
1. **Read the Python source end to end, then enumerate every public
   symbol from the file itself.** Confirm the last line read is EOF, not
   a tool clip; continue with ranged reads (`sed -n`, `tail`) if clipped.
   Then build the required-symbol checklist from the **Python source
   file**, not from the task statement's example list:

   ```bash
   # Enumerate every public top-level symbol in the Python source
   grep -nE '^class |^def |^[A-Z_][A-Z_0-9]* = ' <python-file>
   ```

   The task statement's class/function list is **non-exhaustive by
   default**. Open-ended wording ("all classes", "every function",
   "i.e. X, Y, Z", "e.g. X, Y, Z", a bare parenthesized list) means
   every public symbol in the Python file is required, with the quoted
   list as examples. Only closed-list wording ("only the following
   classes", "exactly these", "limited to") scopes the required set to a
   subset. When the task's list and the Python file disagree, trust the
   Python file.

   Read `references/enumerate-python-symbols.md` when the task statement
   contains a parenthesized or inline class/function list, or when you
   are tempted to drop a Python class because it is not named in the
   task. Skip when the task explicitly uses closed-list wording and the
   closed set is tiny (≤ 3 symbols).
2. **Record each symbol's signature AND each observable output value.**
   For every entry in the checklist from step 1, record exact name
   (preserve underscores), accepted argument types (including
   union-typed params), **return type**, defaults, and (for enums)
   **member identifiers verbatim** AND **`.value` strings verbatim**.
   Then — on pole (a) or mixed — **run the Python module** on 3–5
   representative inputs covering each `tokenize` overload / enum
   member / metadata-writing path and paste the raw stdout under a
   `# python recorded:` block in your plan. This becomes the source of
   truth for every string literal, metadata key, and enum identifier the
   Scala must produce.

   ```bash
   # Record Python's actual outputs — strings the evaluator will read back
   python3 -c "
   from <module> import <PublicClass>, <PublicEnum>
   for m in <PublicEnum>: print(f'{m.name=} {m.value=!r}')
   t = <PublicClass>().<primary_method>(<representative input>)
   print(f'metadata={t.metadata!r}')
   "
   ```

   Read `references/execute-python-for-ground-truth.md` when the Python
   source stores string literals, enum members, or `type(x).__name__`
   tags that evaluator code may read back. Skip when the Python source
   writes no string literals and exposes no enum members, OR when the
   axis step picked pole (b) with no mixed-case signals.
3. **Verify against the task statement's criteria, not your own tests.**
   Behavioural parity under hand-written tests is necessary but not
   sufficient. Run the pole-specific checklist below:

   - **Pole (a)**: (i) compile the raw-type call-site snippet from your
     required artifact above. The snippet must exercise at least one API
     per class in the Python source and use ONLY Python-shaped types —
     no wrapper ADT, no `.get` on `Try`, no `.right.get` on `Either`, no
     translator-defined helper imports. (ii) Every assertion in the
     smoke test quotes a value from the `# python recorded:` block, not
     a value invented while writing Scala. (iii) Diff every public
     signature against the Python source: same method name, same
     parameter names, same accepted types, **same return type (no
     `Try` / `Either` / function wrapping)**, same `**kwargs`/enum
     shape, **same enum member identifiers verbatim**, **same
     dispatch shape (one entry vs overloads of the same name)**, **no
     added public methods or metadata keys**, **no match arms on
     `Some`/`Success`/`Right` for `Any`-dispatch methods**.
   - **Pole (b)**: tick each non-functional criterion against a concrete
     location in your Scala file: type-safety (no `extends .+\[Any\]`
     where Python has a constrained TypeVar), error channel (no thrown
     exceptions where `Try`/`Either` fits), mutability (no `mutable.*` +
     `var` in a public `*Builder`), enum/field naming
     (`UpperCamelCase` unless the task overrides), locale-safety (explicit
     `Locale.ROOT` on numeric formatting).
   - **Mixed**: run BOTH checklists — pole (b) on the internal
     representation, pole (a) on the public boundary.

   ```bash
   # Fast pole-(a) scan — hits are candidate rewrites
   grep -nE ': (Try|Either|Option)\[|\(String, Any\)\*|\.getClass\.getSimpleName|case (Some|Success|Right)\b|"[a-z]+[A-Z][a-zA-Z]*" ->' Output.scala

   # Fast pole-(b) scan
   grep -nE '\[Any\]|throw new .*Exception|mutable\.(ListBuffer|Map|Set)|"%\.[0-9]+f"|case object [A-Z_]{2,}' Output.scala
   ```

   If any check fails: do not submit. Return to the corresponding section
   below and apply the fix before re-running the check.

   Read `references/verify-against-task-criteria.md` for the full
   verification procedure, including a worked pole-(a) example that
   derives the raw-type snippet from a task statement listing named APIs,
   the §1.5 Python-output recording procedure, and the parallel pole-(b)
   checklist with per-item remediations. Skip when the pole-specific
   checklist above passes clean on first run AND (pole-a only) every
   smoke-test assertion is traceable to a recorded Python value.

## Preserve the Python public API shape (pole-a rules)

Apply when the axis step picked **pole (a)** or **mixed** (at the public
boundary). Evaluator-visible divergences — not behavioral bugs — are the
dominant failure mode on pole (a). All of the rules below share one
mechanism: **the evaluator writes the Python identifier/shape AND reads
the Python string spelling; your Scala must accept and produce them
unchanged**. The rules fall into two bands — identifiers (signatures,
member names) and values (string literals, dispatch shapes, added APIs).

### Identifier-level rules

- **Union-typed parameters (`A | B`)** → use method overloads or an
  `Any`-typed parameter with internal pattern match. Do **not** force
  the caller to wrap values in a sealed ADT.
- **Runtime-dispatch classes stay as one class.** A Python class that
  dispatches on `isinstance` under one class name becomes **one** Scala
  class, not a parametric `Foo[A: Numeric]`.
- **Return types verbatim.** If Python returns `T`, Scala returns `T` —
  every wrapping form breaks pole (a): `Try[T]`, `Either[E, T]`,
  `Option[T]` (when Python returns raw `T`), and **function-returning**
  (`T => R` or `T => Either[E, R]` in place of `R`). If error-channel
  idiomaticity is desired, add a parallel `methodTry` / `methodEither`;
  leave the primary `method: T` untouched.
- **`**kwargs` → `Map[String, Any]` or named case class, not
  `(String, Any)*` varargs.** Varargs force tuple-literal call sites
  that Python-shaped evaluator scripts do not write.
- **Python `Enum` → `scala.Enumeration` or Scala-3 `enum`**, not a
  hand-rolled `sealed trait + case object` hierarchy.
- **Enum member identifiers are public API — copy them character-for-
  character from the Python source.** If Python writes `STRING`, Scala
  writes `STRING` (not `String`). Scala accepts SCREAMING_CASE
  identifiers; the `UpperCamelCase`-on-enum-members preference is
  pole-(b)-ONLY. **If you are tempted to write `TokenType.String`
  instead of `TokenType.STRING`, STOP and re-read
  `references/preserve-python-api.md` §9.**
- **Constructor parameter names and types.** Preserve the Python name
  verbatim when the evaluator may call by keyword; change at most one of
  {name, type} per parameter.
- **Idiomatic renames are opt-in.** `snake_case` → `camelCase` is safe
  only when the evaluator does not key on the Python name.
- **No mid-task paradigm swaps.** Fix a failing overload locally; do not
  flip a type class into a subtype trait.

### Value-level rules (iter_4 additions)

- **String-literal values verbatim — identifier renames stop at the
  opening quote.** `with_metadata` → `withMetadata` is an identifier
  rename (allowed when the task names the method in camelCase). But
  `metadata["original_type"]` is a *string value* stored in the map,
  not an identifier — the characters `original_type` are observable
  output, and the camelCase convention does not cross the identifier
  boundary. Likewise, when Python stores `type(x).__name__`, store the
  Python lowercase name (`"int"`, `"float"`, `"str"`, `"bytes"`,
  `"bool"`, `"list"`, `"dict"`, `"tuple"`), **not**
  `value.getClass.getSimpleName` (which returns the capitalised JVM
  form).
- **Dispatch shape preserved.** A Python class with ONE primary method
  dispatching `A | B` through `isinstance` stays ONE Scala class with
  ONE primary entry point. Overloads of the same method name sharing a
  common dispatch path are acceptable; `extends BaseTokenizer[A]`
  demoting the `B` branch to a non-primary overload is NOT the same
  shape.
- **No public-API additions.** The Scala public symbol set equals the
  Python public symbol set, counted exactly. "Convenience" methods
  (`tokenizeToStrings`, `tokenizeWithPositions`, `countTokens`) and
  extra metadata keys (`"position"`, `"original"`) not in the Python
  source are additions, not idiomatic translations. Make internal
  helpers `private`.
- **No match arms on Scala-only types.** Do not add `case Some(v) =>`,
  `case Success(v) =>`, `case Right(v) =>` branches when the Python
  source has no `Option` / `Try` / `Either` concept. The arms of a
  dispatch match are exactly the Python `isinstance` checks in the
  source.

```scala
// Generic pattern — preserve Python signature `foo(value: A | B) -> R`:

// Return type stays R (not Try[R], Either[E, R], or T => Either[E, R]);
// throw on error as Python does.
class Foo extends BaseFoo {   // base class NOT type-parametrized when
                              // Python's base has no Generic[T]
  // Fix A: overloads of the same name (preferred for 2–3 closed arms),
  // both reachable through one dispatch:
  def op(value: Any): Result = value match {
    case a: TypeA => ???
    case b: TypeB => ???
    case other    => throw new IllegalArgumentException(s"Unsupported: $other")
  }

  // Optional parallel error-channel method — DO NOT change the primary:
  def opTry(value: Any): Try[Result] = Try(op(value))

  // Private helpers only — no public convenience methods not in Python:
  private def helper(x: Result): Result = ???
}

// Python `def with_metadata(self, **kwargs)` → Map, not varargs; and
// string-literal keys stay as the Python source writes them:
class Thing(val metadata: Map[String, Any] = Map.empty) {
  def withMetadata(m: Map[String, Any]): Thing =
    new Thing(metadata ++ m)
  // When writing metadata inside a method body, copy keys from the
  // Python source character-for-character:
  def tagType(v: Any): Thing = withMetadata(Map(
    "original_type" -> pythonTypeName(v),   // key verbatim; value from §10b table
  ))
}

// Python Enum member names stay verbatim on pole (a):
object MyType extends Enumeration {
  val FIRST, SECOND, THIRD = Value   // NOT First, Second, Third
}
```

Read `references/preserve-python-api.md` when the task names Python public
symbols with union types, keyword constructor parameters, runtime
`isinstance` dispatch, `**kwargs`, `Enum` subclasses, enum member
identifiers, any wrapping form of return (`Try`/`Either`/function-
returning), **string literals used as metadata keys / type tags**,
**single-entry-point dispatch**, or when you are tempted to add a
"convenience" method, an extra metadata key, or a `case Some(_) =>` arm
not present in the Python source. Skip when the axis step picked pole (b)
with no mixed-case signals.

Read `references/execute-python-for-ground-truth.md` when you are about
to write a Scala assertion or a Scala method body that stores a string
literal derived from the Python source. Skip when the Python source
writes no string literals and exposes no `.value` / `.name` / `__name__`
tags.

## Idiomatic Scala expressions of Python TypeVars (pole-b rules)

Apply when the axis step picked **pole (b)** or **mixed** (in internals).
When the Python source encodes `TypeVar(...)` with distinct per-subclass
constraints, do **not** translate to `BaseFoo[Any]` + `isinstance`-style
match — that is the exact word-to-word form the grader penalizes. Pick one
of four idiomatic expressions:

1. **Bounded type parameter per subclass** — one Scala class per concrete
   Python arm.
2. **Sealed ADT as the type parameter** — closed set of arms, one subclass
   handling all with exhaustive match.
3. **Type class constraint** (`[T: Numeric]`) — numeric-bounded TypeVar,
   one instance per element type.
4. **Scala-3 union type** — small `A | B` union on Scala 3.

```scala
// Generic pattern — Python `class Foo(BaseFoo[T])` with `T` constrained:

// Option 1: bounded subclass per concrete arm
class FooStr   extends BaseFoo[String]       { def op(v: String): R       = ??? }
class FooBytes extends BaseFoo[Array[Byte]]  { def op(v: Array[Byte]): R  = ??? }

// Option 3: type class constraint
class NumFoo[T: Numeric] extends BaseFoo[T] {
  def op(v: T): R = { val n = implicitly[Numeric[T]].toDouble(v); ??? }
}
```

Pair the generics choice with the pole-(b) companion rules:

- **Error channel**: return `Try[T]` / `Either[E, T]` instead of throwing
  `IllegalArgumentException` at public methods.
- **Public builder**: a case class with `copy(...)` methods, not
  `mutable.ListBuffer` + `var`.
- **Enum member casing**: `UpperCamelCase` (`case object String extends
  TokenType`), not Python `SCREAMING_CASE`, unless the task shows a Python
  call site that relies on the Python form.
- **Locale on formatting**: `String.format(Locale.ROOT, "%.3f", x)` and
  `DateTimeFormatter.ofPattern(p, Locale.ROOT)`.

Read `references/scala-generics-for-python-typevars.md` for the full
decision rule across the four options and worked examples of each
companion rule. Skip when the axis step picked pole (a) with no mixed-case
signals — in that case `Any`+match is the correct choice and this chapter
does not apply.

## Core Principles (idiomatic Scala — subject to the axis choice)

When translating Python to Scala, aim for idiomatic Scala, not literal translation:

1. **Prefer immutability** - Use `val` over `var`, immutable collections
2. **Expression-based** - Everything returns a value, minimize statements
3. **Type safety** - Leverage Scala's type system, avoid `Any`
   *(pole-(a) exception: `Any` is correct for Python union-typed
   parameters — see "Preserve the Python public API shape" above)*
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

Note on scope: sealed hierarchies model **the translator's own domain
types** AND are the idiomatic answer when the task is pole-(b) and the
Python source has a constrained TypeVar. Do **not** retrofit a sealed
hierarchy around a parameter whose Python type is `A | B` on a pole-(a)
task — that forces every caller to wrap in your ADT. Do **not** convert a
Python `Enum` subclass to a sealed trait + case objects on pole (a); use
`scala.Enumeration` or Scala-3 `enum` so the shape (members, `.value`,
`.name`, iteration) matches.

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
```

## Scala Naming Conventions

| Python | Scala (idiomatic, pole-b) | Pole-(a) caveat |
|--------|---------------------------|-----------------|
| `snake_case` locals/privates | `camelCase` | always safe |
| `snake_case` public method/field | `camelCase` | safe only if the evaluator does not key on the Python name; when in doubt declare both — see `references/preserve-python-api.md` §4 |
| `snake_case` constructor kwarg | `camelCase` | **keep `snake_case`** when the evaluator may call by keyword; see §3 of the reference |
| `SCREAMING_SNAKE` Python Enum member (e.g. `TokenType.STRING`) | `UpperCamelCase` (e.g. `TokenType.String`) | **keep SCREAMING_CASE verbatim on pole (a).** The identifier (`TokenType.STRING`) is public API — callers write it as-is. Scala accepts SCREAMING_CASE identifiers; "un-Scala to keep SCREAMING_CASE" is a pole-(b) justification only. See `references/preserve-python-api.md` §9. |
| `SCREAMING_SNAKE` true module constant | `UPPER_CASE` or `UpperCamelCase` | prefer `UPPER_CASE` on pole (a) when the evaluator may reference by name |
| `PascalCase` classes | `PascalCase` | always safe |
| `_private` | `private` keyword | safe |
| `"snake_case"` **string literal** (dict key, type tag, enum `.value`) | **copy verbatim** on both poles — the characters inside the quotes are a *value*, not an identifier; the camelCase convention does not cross the opening quote | See `references/preserve-python-api.md` §10. |

## Avoid Returning Unit

```python
# Python - None return is common
def save_user(user):
    db.save(user)
    # implicit None return
```

```scala
// Scala - consider returning useful information
def saveUser(user: User): Either[Error, UserId] = ???

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

## Common Pitfalls

- **Skipping the axis-pick step and defaulting to pole (b).** The ambient
  tone of these skill files pulls toward "idiomatic". If the task names
  public APIs verbatim and says "do the same thing" / "same classes/
  functions" / "must have all classes and functions in the python code",
  those signals override the tone — the task is pole (a). Always write
  the four required-artifact lines before any Scala; the workflow-step-0
  gate refuses to proceed without them.
- **Evaluator-shape divergence on pole (a) — identifier band.** Wrapping
  Python union-typed arguments in a sealed ADT (`StringLike`,
  `StrOrBytes`, `NumericValue`, `TemporalValue`, etc.); wrapping
  Python-returns-raw in `Try[T]` / `Either[E, T]` / `Option[T]` / a
  returned function (`T => Either[E, R]` in place of `R`); converting
  Python `**kwargs` to `(String, Any)*` varargs; converting Python
  `Enum` to `sealed trait + case object`; **renaming Python enum
  members from SCREAMING_CASE to UpperCamelCase (iter_3+iter_4
  recurrence — the identifier `TokenType.STRING` is public API, not
  formatting);** silently dropping Python classes not named in a
  parenthesized "i.e." list in the task statement. All share one
  mechanism: the evaluator writes the Python identifier; your Scala must
  accept it unchanged.
- **Evaluator-value divergence on pole (a) — value band (iter_4).**
  Camel-casing a string literal used as a dict key or type tag
  (`"originalType"` where Python writes `"original_type"`); storing
  `value.getClass.getSimpleName` where Python stores
  `type(value).__name__` (JVM `"Int"` vs Python `"int"`); demoting one
  branch of a `str | bytes` dispatch to a non-primary overload under
  `extends BaseTokenizer[String]`; adding "convenience" public methods
  (`tokenizeToStrings`, `countTokens`) or extra metadata keys
  (`"position"`, `"original"`) that have no Python counterpart; adding
  `case Some(_) =>` / `case Success(_) =>` / `case Right(_) =>` arms to
  an `Any`-dispatch method whose Python counterpart has no corresponding
  type. These share one mechanism: identifier-level renames must stop
  at the identifier boundary, dispatch shapes must match, and the public
  symbol set equals Python's exactly.
- **Flattening a typed hierarchy to `[Any]` on pole (b).** When the Python
  source has `BaseFoo[T]` with distinct per-subclass constraints, use
  bounded subclasses / sealed ADTs / type classes — see
  `references/scala-generics-for-python-typevars.md`.
- **Simultaneously renaming AND retyping a constructor parameter.** Change
  at most one at a time; prefer keeping both when the evaluator may call
  by keyword.
- **Translating a class whose Python source you have not read, OR
  enumerating required symbols from the task statement's example list
  instead of the Python file.** Invented method names and parameters are
  the first tell; dropped classes are the second. Return to the Python
  source, confirm EOF, and `grep -nE '^class |^def '` to enumerate.
- **Tautological verification — compile check passed, values wrong.**
  Previously the agent used translator-defined wrapper types in its
  smoke test; iter_4 shows a newer form where the raw-type call sites
  compile clean (`new StringTokenizer().tokenize("hello")`) but the
  smoke-test assertions quote values the agent invented while writing
  Scala (`metadata("originalType") == "Int"`) rather than values from
  running the Python module (`metadata("original_type") == "int"`).
  Both forms fail for the same reason: the test exercises only the
  agent's own mental model of the API, not the Python source's actual
  behaviour. Fix: on pole (a), paste a `# python recorded:` block from
  running the Python module (step 2) into the plan, and quote every
  smoke-test assertion from the recording. On pole (b), run the
  non-functional checklist — behavioural tests do not catch `[Any]`
  flattening, thrown exceptions, `mutable.*` builders, SCREAMING_CASE
  enums (where UpperCamelCase was requested), or default-locale
  formatting.
- **Mid-task paradigm swaps to dodge a compile error.** Fix the overload
  locally (rename, disambiguate) rather than flipping a type class into a
  subtype trait.
- **Default-locale numeric formatting.** `"%.3f".format(x)` produces a
  decimal comma on non-US locales. Use `String.format(Locale.ROOT, ...)`
  on pole-(b) tasks.

## Anti-Patterns to Avoid

```scala
// DON'T: Use null
val name: String = null  // Bad!

// DO: Use Option
val name: Option[String] = None

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
```
