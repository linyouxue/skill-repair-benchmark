# Verifying a Python→Scala translation against the task statement

A Scala translation that compiles cleanly and passes a hand-written smoke
test can still score 0. The five recurring failure modes:

- **iter_0, iter_2, iter_3 (pole-a tasks):** the agent's smoke test used
  its own invented wrapper ADTs (`StrOrBytes.Str("hi")`,
  `StringLike.Str("hi")`, `TemporalValue.DateTime(...)`,
  `NumericValue.IntVal(3)`) and called `.get` on `Try` returns /
  `.right.get` on `Either` returns. The test tautologically passed and
  did not detect that the evaluator's raw-type call sites
  (`new StringTokenizer().tokenize("hello"): Token`,
  `TokenType.STRING: TokenType`,
  `(new TokenizerBuilder).build: BaseTokenizer`) would not compile.
- **iter_1 (pole-b task):** the smoke test verified behavioural parity
  only; it did not detect `[Any]` flattening, thrown exceptions where
  `Try`/`Either` was requested, `mutable.ListBuffer` + `var` builder
  internals, SCREAMING_CASE enum members, or locale-dependent format
  calls — all of which the task explicitly asked for.
- **iter_4 (pole-a task) — NEW form:** the raw-type call-site snippet
  compiled clean (`new StringTokenizer().tokenize("hello")` — no wrapper
  ADTs, no `.get`), but the smoke test asserted against values the agent
  **invented while writing Scala** (`token.metadata("originalType") ==
  "Int"`, `TokenType.String.toString == "String"`) rather than values
  obtained by running the Python module (`metadata["original_type"] ==
  "int"`, `TokenType.STRING.name == "STRING"`). The compile check passed;
  the tautological assertion passed; and string-literal + enum-identifier
  drift stayed invisible. **A compile-check gate alone is insufficient on
  pole (a) — the verification must also compare observable output values
  byte-for-byte against the Python module.**

The common root cause: the verification pass asked "does my code run?"
not "does my code produce the strings the Python module produces?". A
raw-type call-site snippet derived from the task statement catches
shape; a Python-output recording catches values. Pole (a) needs both.

Read this chapter before every "I'm done" moment on a translation task.
Skip only when the required-artifact lines in
`references/task-statement-axis-calibration.md` §1 are filled AND the
pole-specific checklist in SKILL.md workflow step 3 passed clean on
first run AND (pole-a only) the Python-output recording is pasted in
the plan with every smoke-test assertion traceable to a recorded value.

---

## 1. Pole-(a) verification — raw-type call-site snippet

**Derive the snippet from the task statement, not from your own code.**

The snippet is **not** your smoke test. Your smoke test uses whatever
helper objects you defined; this snippet uses only what the task statement
and the Python source expose.

### Snippet construction procedure

```
1. Open the task statement. Copy the list of named public APIs. Then open
   the Python source and enumerate every public class — the task's list
   is non-exhaustive (see `references/enumerate-python-symbols.md`).
2. For each named API AND for at least one API per class in the Python
   source, write one call-site line using ONLY Python-shaped types from
   the Python source signature:
     - String arguments as `"literal"`, not `StrOrBytes.Str("literal")`
       or `StringLike.Str("literal")`
     - Byte-string arguments as `"literal".getBytes` or `Array[Byte](...)`,
       not `StrOrBytes.Bytes(...)`
     - Numeric arguments as `3`, `3.14`, `BigDecimal("1.0")`, not
       `NumericValue.IntVal(3)`
     - Date/time arguments as `LocalDate.now()`, `LocalDateTime.now()`,
       not `TemporalValue.Date(...)`
     - Keyword arguments as named parameters or a `Map`: `foo(key = value)`
       or `foo(Map("key" -> value))`, not tuple-vararg literals
       `foo("key" -> value)`
     - Enum members by their **Python identifier verbatim**
       (`TokenType.STRING`, not `TokenType.String`)
3. Ascribe the expected return type (`: Token`, not `: Try[Token]` or
   `: Either[String, Token]` or `: Any => Either[String, Token]`).
4. Compile the snippet. Every line must type-check.
```

### Worked example — derived from iter_2/iter_3 task statement

**Task statement quote:** "The Scala translation must have all classes
and functions in the python code (i.e. `tokenize`, `tokenizeBatch`,
`toToken`, `withMetadata`, `TokenType`, …) and do the same thing."

**Python source signatures (step 1):**

```python
class StringTokenizer(BaseTokenizer):
    def tokenize(self, value: str | bytes) -> Token: ...

class TemporalTokenizer(BaseTokenizer):
    def tokenize(self, value: datetime | date) -> Token: ...

class BaseTokenizer:
    def tokenize_batch(self, values: Iterable) -> Iterator[Token]: ...

class Tokenizable:
    def to_token(self) -> Token: ...

class Token:
    def with_metadata(self, **kwargs) -> "Token": ...

class TokenType(Enum):
    STRING = "string"; NUMERIC = "numeric"; ...

class TokenizerBuilder:
    def build(self) -> BaseTokenizer: ...
```

**Raw-type call-site snippet (step 2–4):**

```scala
import java.time.{LocalDate, LocalDateTime}

object EvaluatorStyleCallSites {
  // Each line uses ONLY Python-shaped types. Compile this file in your
  // build; if any line fails, see corrective step below.

  val st = new StringTokenizer()
  val t1: Token = st.tokenize("hello")                   // §1 of preserve-python-api
  val t2: Token = st.tokenize("hi".getBytes)             // §1

  val tt = new TemporalTokenizer()
  val t3: Token = tt.tokenize(LocalDate.now())           // §1
  val t4: Token = tt.tokenize(LocalDateTime.now())       // §1

  // tokenizeBatch returns Iterator[Token], NOT Iterator[Try[Token]]:
  val batch: List[Token] = st.tokenizeBatch(List("a", "b").iterator).toList  // §6

  // withMetadata accepts a Map (or named kwargs via a case class),
  // NOT (String, Any)* varargs:
  val base: Token = ???
  val t5: Token = base.withMetadata(Map("source" -> "user",
                                        "confidence" -> 0.9))                // §7

  // Enum member by Python identifier verbatim — catches member renames:
  val tt1: TokenType = TokenType.STRING                                      // §9
  val tt2: TokenType = TokenType.NUMERIC                                     // §9

  // Builder returns a BaseTokenizer directly — NOT T => Either[E, Token]:
  val built: BaseTokenizer = (new TokenizerBuilder).build                    // §6
}
```

### Corrective step on failure

If any line fails to compile, trace it to one of these causes and apply
the corresponding section of `references/preserve-python-api.md`:

| Compile error pattern | Cause | Fix |
|---|---|---|
| `type mismatch; found String, required StrOrBytes/StringLike/...` | wrapper ADT around union-typed input | §1: overloads or `Any`+match |
| `type mismatch; found Try[Token], required Token` on return ascription | return wrapped in `Try`/`Either` | §6: unwrap return; add parallel `methodTry` if desired |
| `type mismatch; found Any => Either[String, Token], required BaseTokenizer` | function-returning builder | §6: return the raw type (e.g. `BaseTokenizer`), not a function |
| `too many arguments for method withMetadata` on named kwargs | `(String, Any)*` varargs | §7: switch to `Map[String, Any]` or named case class |
| `TokenType.values is not a member` or missing `.name` | hand-rolled sealed-trait enum | §8: switch to `scala.Enumeration` or Scala-3 `enum` |
| `value STRING is not a member of object TokenType` | enum member renamed from Python SCREAMING_CASE | §9: rename Scala identifier back to Python form |
| `cannot resolve symbol tokenizeBatch` or wrong camelCase/snake_case | rename of evaluator-probed symbol | §4: add snake_case alias or revert the rename |
| `too many methods / value tokenizeToStrings not in Python source` | public-API addition | §12: delete the extra method or make it `private` |
| overload resolution picks `tokenize(String)` but Python test calls on `Any` | dispatch-shape divergence (parametric base) | §11: remove type parameter from base, widen primary to `Any`+match |

After the fix, re-run the snippet. Do **not** submit until every line
compiles clean.

### Negative examples — what is NOT a raw-type call-site snippet

```scala
// NOT a raw-type snippet — uses translator-defined wrapper ADT (iter_0, iter_2, iter_3):
val t = new StringTokenizer().tokenize(StrOrBytes.Str("hi"))
val t = new StringTokenizer().tokenize(StringLike.Str("hi"))     // iter_3 variant
val t = new NumericTokenizer().tokenize(NumericValue.IntVal(3))  // iter_3 variant

// NOT a raw-type snippet — calls .get on a Try return (iter_2):
val t = new StringTokenizer().tokenize("hi").get

// NOT a raw-type snippet — calls .right.get on an Either return (iter_3):
val t = new StringTokenizer().tokenize("hi").right.get

// NOT a raw-type snippet — passes to a function-returning builder (iter_3):
val t = (new TokenizerBuilder).build.apply("hi").right.get

// NOT a raw-type snippet — constructs a translator-defined helper:
val t = new TemporalTokenizer().tokenize(TemporalValue.DateTime(LocalDateTime.now()))

// NOT a raw-type snippet — passes tuple literals to varargs:
val t = Token().withMetadata("source" -> "user", "confidence" -> 0.9)

// NOT a raw-type snippet — uses renamed enum member:
val t: TokenType = TokenType.String   // iter_3 renamed STRING → String
```

Each of the above exercises the diverged API and tells you nothing about
whether the evaluator's call sites will succeed.

---

## 1.5. Pole-(a) verification — Python-output recording (NEW iter_4)

**The compile check catches shape; it does not catch values.** The
iter_4 agent passed §1 cleanly (raw-type call sites compiled) but
asserted against values it invented while writing Scala
(`"originalType"` / `"Int"` / `TokenType.String`), where Python actually
produces `"original_type"` / `"int"` / `TokenType.STRING`. The smoke
test tautologically passed; the grader scored 0.

**On pole (a), run the Python module before writing Scala assertions.**

See `references/execute-python-for-ground-truth.md` for the full
procedure. Short version:

1. Write a 10-line Python script that constructs 3–5 representative
   inputs covering every `tokenize` overload / enum member / metadata-
   writing path in the Python source, and prints `.repr` of each
   output (metadata dict, enum `.name`, enum `.value`,
   `type(x).__name__`).
2. Run it with `python3 record.py` and paste raw stdout under a
   `# python recorded:` block in the plan.
3. Every assertion in your Scala smoke test quotes a value from the
   recording — with a comment pointing to the recorded line.

### Anti-pattern — iter_4 tautological smoke test

```scala
// Compiles. Passes. Grades 0 because the strings are wrong.
val t = new NumericTokenizer().tokenize(42)
assert(t.metadata("originalType") == "Int")   // ❌ invented, not recorded
assert(TokenType.String.toString == "String") // ❌ invented, not recorded
```

### Correct form — assertions quote the recording

```
# python recorded:
# $ python3 -c 'from tokenizer import *; print(repr(NumericTokenizer().tokenize(42).metadata)); print(repr(TokenType.STRING.name))'
# {'original_type': 'int', 'token_type': 'numeric'}
# 'STRING'
```

```scala
val t = new NumericTokenizer().tokenize(42)
assert(t.metadata("original_type") == "int")       // recorded line 1
assert(t.metadata("token_type")    == "numeric")   // recorded line 1
assert(TokenType.STRING.toString == "STRING")      // recorded line 2
```

### Corrective step on failure

If any assertion fires, the Scala method body (not the assertion)
diverged from the Python-recorded value. Rewrite the Scala body to
produce the recorded string, then re-run. If the Scala uses
`.getClass.getSimpleName` where Python uses `type(x).__name__`, replace
with `pythonTypeName(x)` (see `references/preserve-python-api.md` §10b).

---

## 2. Pole-(b) verification — non-functional criteria checklist

Behavioural parity under hand-written tests does not detect any of the
non-functional misses iter_1 made. Tick each item against a concrete
location in your Scala file BEFORE declaring the task done.

### Checklist

- [ ] **Type-safety of generics.** No `BaseFoo[Any]` where the Python
      source has `BaseFoo[T]` with distinct per-subclass constraints —
      see `references/scala-generics-for-python-typevars.md` §1.
- [ ] **Error channel.** No thrown `IllegalArgumentException` /
      `RuntimeException` at a public method boundary where the task says
      "handle errors naturally"; return `Try[T]` or `Either[E, T]`.
- [ ] **Mutability of public builders.** Classes named `*Builder` do not
      hold `mutable.ListBuffer` + `var`; each method returns a new
      instance via `copy(...)` on a case class or a new `new Builder(...)`
      call.
- [ ] **Enum/field naming.** Enum case objects use `UpperCamelCase`
      (`case object String extends TokenType`), not Python
      `SCREAMING_CASE`, unless the task shows a call site that uses
      `TokenType.STRING`.
- [ ] **Locale-safety.** Any `"%.Nf".format(x)` or `String.format(...)`
      pins `Locale.ROOT`; `DateTimeFormatter` is created with an explicit
      `Locale` where locale-sensitive patterns (`MMM`, `E`) are used.
- [ ] **Immutable internals.** Local `var` + loop replaced with
      `foldLeft`/`scan`/`collect` when the task flags immutability.

### Grep-based fast scan

```bash
grep -nE 'extends .+\[Any\]|throw new .*Exception|mutable\.(ListBuffer|Map|Set)|%\.[0-9]+f|case object [A-Z_]{2,}' Output.scala
```

### Corrective step on failure

For each hit, apply the matching rule from
`references/scala-generics-for-python-typevars.md`:

| Hit pattern | Rewrite rule |
|---|---|
| `extends .+\[Any\]` | §1: bounded generic / sealed ADT / type class / Scala-3 union |
| `throw new .*Exception` at public method | §2a: `Try` or `Either` |
| `mutable.*` inside `*Builder` | §2b: case class with `copy(...)` |
| `"%.Nf"` or default-locale `String.format` | §2c: `Locale.ROOT` |
| `case object [A-Z_]{2,}` in enum | §2 decision rule: rename to `UpperCamelCase` unless the task overrides |

If a hit survives rewrite attempts, re-check the axis
(`references/task-statement-axis-calibration.md`) — the rewrite pressure
may indicate the task is actually mixed, and the hit is a pole-(a)
constraint on the public boundary.

---

## 3. Mixed-mode verification

Run both §1 (raw-type call-site snippet) on the public boundary, §1.5
(Python-output recording) on observable string values, and §2
(non-functional checklist) on the internals. The public class names,
method names, parameter names, accepted types, enum member identifiers,
string-literal values, and return types come from Python; the internal
representation is yours and is judged by §2.

### Decision rule

A pole-(b) rewrite that changes a public signature named in the task
statement is a slip from mixed into pole (b) — the public boundary must
stay pole-(a)-shaped. If `[Any]` on a public method is the only way to
pass §1, keep it; move the type-class dispatch to a private internal
layer.

---

## 4. End-to-end checklist (both poles)

Before submitting, confirm all of the following:

1. The required-artifact lines (named APIs, signal phrase, chosen pole,
   raw-type call sites) are filled at the top of the plan — see
   `references/task-statement-axis-calibration.md` §1.
2. The Python source was read to EOF; every public symbol in the
   **Python source file** (not just the task's example list) was located
   and has a Scala counterpart section — see
   `references/enumerate-python-symbols.md` §3 and §5.
3. For pole (a) or mixed: §1 raw-type call-site snippet compiles clean,
   including at least one line per class in the Python source and at
   least one line exercising an enum member by its Python identifier.
4. For pole (a) or mixed: §1.5 Python-output recording is pasted in the
   plan; every smoke-test assertion quotes a recorded value. See
   `references/execute-python-for-ground-truth.md`.
5. For pole (b) or mixed: §2 checklist is ticked clean (grep returns no
   unjustified hits).
6. Signature + output diff: every public symbol's Scala signature
   matches its Python counterpart on {name, parameter names, accepted
   argument types, return type (no `Try` / `Either` / `Option` /
   function wrapping), kwargs shape, enum shape, enum member
   identifiers, dispatch shape (one entry vs two entries), **string
   literals used as metadata keys / type tags / enum `.value`s**, **no
   added public methods or metadata keys**, **no match arms on
   Scala-only types**} — see `references/preserve-python-api.md`
   §End-to-end.

If any item fails, return to the specific section referenced and apply
the fix before re-running the checklist. Behavioural parity alone is
never sufficient on either pole.
