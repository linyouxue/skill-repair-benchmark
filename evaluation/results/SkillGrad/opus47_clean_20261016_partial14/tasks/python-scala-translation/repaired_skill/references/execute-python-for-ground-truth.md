# Record Python outputs as ground truth before writing Scala assertions

On pole (a), the evaluator compares Scala outputs byte-for-byte against the
Python module's actual outputs — not against the "obvious" values the
translator guesses while writing Scala. Compile-check verification catches
identifier/signature drift (wrapper ADTs, `.get` on `Try`, varargs
`**kwargs`), but it is **silent on string-literal values**: an assertion
`token.metadata("originalType") == "Int"` compiles clean against a Scala
file that stores `"originalType" -> "Int"`, yet both the key and the value
are wrong — Python stores `"original_type" -> "int"`. Compile passes,
smoke test passes, grader scores 0.

The iter_4 recurrence on the Tokenizer family shows this failure mode
exactly: the raw-type call-site snippet (`new StringTokenizer().tokenize(
"hello")`) compiled, but the smoke test asserted against values the agent
invented while writing Scala. Four prior atomic L2 patches on the pole-(a)
rules did not resolve this because the rules describe signatures, not
observable output values.

Read this chapter before writing any Scala assertion on a pole-(a) task,
AND before writing any Scala method body that stores a string literal
derived from the Python source (metadata keys, type-name tags, enum
`.value` strings, error-message prefixes, format patterns). Skip only
when the Python source stores no string literals and exposes no enum
members / `__name__` tags that evaluator code might read.

---

## 1. Procedure — record Python outputs for 3–5 representative inputs

### Step A: enumerate every observable-output path

From the Python source, list every code path that produces a value the
evaluator can observe. Observable-output paths typically include:

- enum `.name` and `.value` for each member;
- every `metadata[...] = ...` assignment inside method bodies;
- every string that uses `type(x).__name__` (the Python type name is
  lowercase: `"int"`, `"float"`, `"str"`, `"bytes"`, `"bool"`, `"list"`,
  `"dict"`, `"tuple"` — distinct from the Scala/JVM capitalised form
  `.getClass.getSimpleName` returns);
- every `f"{...}"` / `str.format(...)` / `__repr__` / `__str__` that
  flows out of a public method;
- every format-string pattern (`"%.3f"`, `"%Y-%m-%d"`).

### Step B: write a small Python script covering each path

```python
# record.py — exercise the Python source on representative inputs and
# print the exact observable outputs.
import sys
sys.path.insert(0, "<python-source-dir>")
from <python_module> import <classes you are translating>

# One block per observable-output path. Print the exact repr/.name/.value
# — do NOT paraphrase or format for readability.

# Enum members
for m in <PythonEnum>:
    print(f"{m.name=} {m.value=!r}")

# Each tokenize overload / each metadata-writing method body
tok = <PythonClass>().tokenize(<representative input>)
print(f"metadata={tok.metadata!r}")        # dict repr — exact key/value spellings
print(f"token_type={tok.token_type!r}")    # field name AND value verbatim

# type(x).__name__ for each type the Python source stores as a tag
for v in [1, 1.5, "s", b"b", True, [], {}, ()]:
    print(f"type({v!r}).__name__ = {type(v).__name__!r}")
```

### Step C: run it and paste the raw stdout into the plan

```bash
python3 record.py > python_recorded.txt
cat python_recorded.txt
```

Paste the full stdout into your plan under a `# python recorded:` heading.
Every subsequent Scala assertion must quote values from this block —
never values invented while writing Scala.

### Step D: write Scala assertions against the recorded values

```scala
// Scala smoke test — EVERY assertion quotes a value from python_recorded.txt
val t = (new NumericTokenizer).tokenize(42)
assert(t.metadata("original_type") == "int")   // recorded: 'original_type' -> 'int'
assert(t.metadata("token_type") == "numeric")  // recorded: 'token_type' -> 'numeric'
assert(TokenType.STRING.toString == "STRING")  // recorded: STRING.name == 'STRING'
```

If any assertion fails: the Scala diverged from the recorded Python
output. Rewrite the Scala method body (not the assertion) to produce the
recorded value, then re-run.

---

## 2. Python-type-name mapping (for `type(x).__name__` paths)

When the Python source stores `metadata[k] = type(value).__name__`, the
stored *value* is the Python lowercase type name. The JVM equivalent
(`value.getClass.getSimpleName`) returns the Scala/Java capitalised form
and is **wrong** on pole (a). Use the mapping below.

| Python expression | Python output | Naive Scala (WRONG) | Correct Scala |
|---|---|---|---|
| `type(1).__name__` | `"int"` | `1.getClass.getSimpleName` → `"Integer"` or `"int"` | `"int"` |
| `type(1.5).__name__` | `"float"` | → `"Double"` | `"float"` |
| `type("s").__name__` | `"str"` | → `"String"` | `"str"` |
| `type(b"b").__name__` | `"bytes"` | → `"byte[]"` | `"bytes"` |
| `type(True).__name__` | `"bool"` | → `"Boolean"` | `"bool"` |
| `type([]).__name__` | `"list"` | → `"ArrayList"` / `"$colon$colon"` | `"list"` |
| `type({}).__name__` | `"dict"` | → `"HashMap"` / `"Map$Map1"` | `"dict"` |
| `type(()).__name__` | `"tuple"` | → `"Tuple0"` / `"Tuple2"` | `"tuple"` |
| `type(None).__name__` | `"NoneType"` | → `"null"` or NPE | `"NoneType"` |

### Helper — `pythonTypeName(value: Any): String`

Define this helper once and use it wherever the Python source stores
`type(x).__name__`:

```scala
object PythonTypeName {
  def pythonTypeName(value: Any): String = value match {
    case null              => "NoneType"
    case _: Boolean        => "bool"       // check Boolean BEFORE Int: a boxed
                                           // Boolean is also an Integer on the JVM
    case _: Byte | _: Short | _: Int | _: Long
                           => "int"
    case _: Float | _: Double
                           => "float"
    case _: Char | _: String
                           => "str"
    case _: Array[Byte]    => "bytes"
    case _: Map[_, _]      => "dict"
    case _: scala.collection.Seq[_] | _: java.util.List[_]
                           => "list"
    case _: Product        => "tuple"     // Tuple2, Tuple3, …
    case other             => other.getClass.getSimpleName.toLowerCase
  }
}
```

### Verification

```scala
// Each line must print the Python-recorded value, not the JVM name.
import PythonTypeName.pythonTypeName
println(pythonTypeName(42))            // "int"       — not "Integer"
println(pythonTypeName(3.14))          // "float"     — not "Double"
println(pythonTypeName("hi"))          // "str"       — not "String"
println(pythonTypeName("hi".getBytes)) // "bytes"     — not "byte[]"
println(pythonTypeName(true))          // "bool"      — not "Boolean"
```

If any line prints the JVM form, the pattern match ordering is wrong
(most commonly: `Boolean` is matching the `Int` arm because of autoboxing).
Reorder so `Boolean` precedes `Int`, re-run.

---

## 3. Anti-pattern — iter_4 tautological smoke test

The iter_4 agent wrote this smoke test:

```scala
// Tautological — assertions quote values the agent invented while
// writing the Scala, not values recorded from the Python module.
val t = new NumericTokenizer().tokenize(42)
assert(t.metadata("originalType") == "Int")   // ❌ invented
assert(TokenType.String.toString == "String") // ❌ invented
```

The Scala code was:

```scala
case class Token(metadata: Map[String, Any] = Map.empty) {
  def withMetadata(m: Map[String, Any]): Token =
    copy(metadata = metadata ++ m)
}

class NumericTokenizer {
  def tokenize(value: Int): Token = Token().withMetadata(
    Map("originalType" -> value.getClass.getSimpleName)  // "Int"
  )
}

enum TokenType(val value: String):
  case String extends TokenType("string")   // identifier renamed
```

Compile passed. Assertions passed. The grader read
`token.metadata["original_type"]` and got `None`; read
`TokenType.STRING` and got a NameError. Score: 0.

### Correct form — assertions quote recorded Python values

Python session recorded first:

```
$ python3 -c '
from tokenizer import NumericTokenizer, TokenType
t = NumericTokenizer().tokenize(42)
print(repr(t.metadata))
print(repr(TokenType.STRING.name), repr(TokenType.STRING.value))
'
{'original_type': 'int', 'token_type': 'numeric'}
'STRING' 'string'
```

Scala rewritten to match:

```scala
class NumericTokenizer {
  def tokenize(value: Int): Token = Token().withMetadata(
    Map("original_type" -> pythonTypeName(value),  // "int" — string key verbatim,
        "token_type"    -> "numeric")              //         value from mapping
  )
}

// Scala 3:
enum TokenType(val value: String):
  case STRING   extends TokenType("string")  // identifier verbatim
  case NUMERIC  extends TokenType("numeric")
  case TEMPORAL extends TokenType("temporal")

// Smoke test — every assertion quotes a value from the recorded output
val t = new NumericTokenizer().tokenize(42)
assert(t.metadata("original_type") == "int")        // recorded
assert(t.metadata("token_type")    == "numeric")    // recorded
assert(TokenType.STRING.toString == "STRING")       // recorded via .name
```

---

## 4. End-to-end checklist

Before writing any Scala assertion on a pole-(a) task:

1. The plan contains a `# python recorded:` block with raw stdout from
   running the Python module on 3–5 representative inputs covering:
   - every enum member's `.name` and `.value`;
   - every `tokenize` / `withMetadata` / method-that-writes-metadata path;
   - at least one path per `type(x).__name__` tag the Python source stores.
2. Every string literal in your Scala method bodies that originates in
   the Python source (metadata keys, type tags, enum `.value` strings,
   error-message prefixes, format patterns) is a byte-for-byte copy of
   the Python-recorded string — not a camelCased or JVM-renamed variant.
3. Every assertion in your smoke test quotes a value from the recorded
   block, with a comment pointing to the recording.
4. The `pythonTypeName` helper (or an inlined equivalent) is used
   wherever Python stores `type(x).__name__`; `.getClass.getSimpleName`
   does not appear in any method body that writes to metadata on pole (a).

### Corrective step on failure

- Missing `# python recorded:` block → go to §1 Step B, write the script,
  run it, paste the stdout, THEN return to Scala.
- Any assertion value not traceable to the recorded block → rewrite the
  assertion to quote a recorded value. If the recorded value differs from
  what the Scala currently produces, fix the Scala method body (not the
  assertion).
- `.getClass.getSimpleName` on a value whose Python counterpart uses
  `type(x).__name__` → replace with `pythonTypeName(x)`; re-run the
  smoke test.
- A metadata key or enum `.value` differs from the recorded string by
  case alone (`"originalType"` vs `"original_type"`, `"Int"` vs `"int"`)
  → rewrite the Scala literal to match the recording character-for-
  character. See also `references/preserve-python-api.md` §10
  (string-literal values verbatim).
