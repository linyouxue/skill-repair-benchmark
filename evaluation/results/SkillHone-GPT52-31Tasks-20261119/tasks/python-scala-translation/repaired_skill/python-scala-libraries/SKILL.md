---
name: python-scala-libraries
description: Guide for mapping common Python libraries and idioms to Scala equivalents. Use when converting Python code that uses standard library modules (json, datetime, os, re, logging) or needs equivalent Scala libraries for HTTP, testing, or async operations.
---

# Python to Scala Library Mappings

## Dependency / build constraints (important)

When translating Python to Scala in an evaluation or “single-file compile” setting, assume **only the Scala standard library + JDK** are available unless the task explicitly provides a build (sbt/mill) and dependencies.

Guidelines:

- Prefer **`java.*` / `javax.*`** and Scala stdlib (`scala.*`).
- Avoid libraries like Circe / Play JSON / sttp / cats-effect unless you are sure they are on the classpath.
- If you need JSON, config, CLI parsing, etc. and no deps are allowed, implement a **small, well-scoped utility** that covers only the value types your Python code actually produces.

## JSON Handling

### Preferred when dependencies are available

If the project uses sbt/mill and already includes a JSON library, use it.

If you are writing a **single Scala file that must compile in isolation**, do **not** import Circe/Play JSON; implement a small JSON utility instead.

```python
# Python
import json

data = {"name": "Alice", "age": 30}
json_str = json.dumps(data)
parsed = json.loads(json_str)

# With dataclass
from dataclasses import dataclass, asdict

@dataclass
class Person:
    name: str
    age: int

person = Person("Alice", 30)
json.dumps(asdict(person))
```

```scala
// Scala - circe (popular, but requires a dependency)
import io.circe._
import io.circe.generic.auto._
import io.circe.syntax._
import io.circe.parser._

case class Person(name: String, age: Int)

val person = Person("Alice", 30)
val jsonStr: String = person.asJson.noSpaces
val parsed: Either[Error, Person] = decode[Person](jsonStr)

// Scala - play-json (also requires a dependency)
import play.api.libs.json._

case class Person(name: String, age: Int)
implicit val personFormat: Format[Person] = Json.format[Person]

val json = Json.toJson(person)
val parsed = json.as[Person]
```

### When no dependencies are allowed

Use a minimal in-file JSON renderer/parser that only supports the subset you need.

- Rendering: build JSON strings from `Map[String, Any]`, `List[Any]`, primitives, and `null`.
  - Prefer `ListMap` / `LinkedHashMap` (or an explicit `List[(String, Any)]`) if you must preserve insertion order.
- Parsing: if unavoidable, prefer a very small recursive descent parser for objects/arrays/strings/numbers/bools/null.
- Keep it isolated (e.g., `object Json` with an ADT `sealed trait JsonValue`) and covered by a few examples.

### Matching Python `json.dumps` semantics (important)

If the Python code uses `json.dumps(...)` and the resulting string is user-visible or tested, match Python’s parameters and defaults rather than “prettifying” output.

Key points to verify in the Python source:

- `ensure_ascii` defaults to `True`: non-ASCII characters are escaped as `\uXXXX`. If the Python code does **not** set `ensure_ascii = False`, your Scala renderer should escape non-ASCII too (not just control characters).
- `separators` default to `(", ", ": ")` (note the spaces). Pretty printing with `indent = N` uses newlines and `N` spaces per nesting level.
- `sort_keys` defaults to `False`: keep the input object key order when possible. If you need deterministic ordering in Scala, prefer representing objects as `Seq[(String, JsonValue)]` / `ListMap` / `LinkedHashMap` rather than sorting keys (unless the Python code sets `sort_keys = True`).
- Python renders booleans/null as `true`/`false`/`null` (lowercase).

Rule of thumb: only change key ordering, whitespace, or Unicode escaping if you can confirm the Python side does the same.

## Date and Time

```python
# Python
from datetime import datetime, date, timedelta
import pytz

now = datetime.now()
today = date.today()
specific = datetime(2024, 1, 15, 10, 30)
formatted = now.strftime("%Y-%m-%d %H:%M:%S")
parsed = datetime.strptime("2024-01-15", "%Y-%m-%d")

# Note: Python `strftime` uses `%`-directives; these are *not* compatible with Java/Scala
# `DateTimeFormatter` patterns.
# - When you build a Java/Scala pattern string, **any ASCII letter** (A–Z / a–z) is interpreted as a pattern symbol.
#   If you want a literal letter (common in ISO-8601 separators like `T`), wrap it in single quotes: `'T'`.
#   To include a literal single quote, escape it by doubling: `''`.
tomorrow = now + timedelta(days=1)

# Timezone
utc_now = datetime.now(pytz.UTC)
```

```scala
// Scala - java.time (recommended)
import java.time._
import java.time.format.DateTimeFormatter

val now = LocalDateTime.now()
val today = LocalDate.now()
val specific = LocalDateTime.of(2024, 1, 15, 10, 30)

// Java/Scala formatter patterns differ from Python's strftime directives.
// If you need to replicate Python's "%Y-%m-%d %H:%M:%S", use the equivalent Java pattern:
// (Reminder: literal letters in DateTimeFormatter patterns must be quoted, e.g. "yyyy-MM-dd'T'HH:mm:ss".)
val formatted = now.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))

val parsed = LocalDate.parse("2024-01-15")
val tomorrow = now.plusDays(1)

// Timezone
val utcNow = ZonedDateTime.now(ZoneOffset.UTC)
val instant = Instant.now()
```

## File Operations

```python
# Python
from pathlib import Path
import os

# Reading
with open("file.txt", "r") as f:
    content = f.read()
    lines = f.readlines()

# Writing
with open("file.txt", "w") as f:
    f.write("Hello")

# Path operations
path = Path("dir/file.txt")
path.exists()
path.parent
path.name
path.suffix
list(Path(".").glob("*.txt"))
os.makedirs("new/dir", exist_ok=True)
```

```scala
// Scala - java.nio.file (standard) + scala.io
import java.nio.file.{Files, Path, Paths}
import scala.io.Source
import scala.util.Using

// Reading
val content = Source.fromFile("file.txt").mkString
Using(Source.fromFile("file.txt")) { source =>
  source.getLines().toList
}

// Writing
Files.writeString(Paths.get("file.txt"), "Hello")

// Path operations
val path = Paths.get("dir/file.txt")
Files.exists(path)
path.getParent
path.getFileName
// Extension: path.toString.split('.').lastOption
Files.createDirectories(Paths.get("new/dir"))

// os-lib (better alternative)
// import os._
// os.read(os.pwd / "file.txt")
// os.write(os.pwd / "file.txt", "Hello")
```

## Regular Expressions

```python
# Python
import re

pattern = r"\d+"
text = "abc123def456"

# Search
match = re.search(pattern, text)
if match:
    print(match.group())

# Find all
matches = re.findall(pattern, text)

# Replace
result = re.sub(pattern, "X", text)

# Split
parts = re.split(r"\s+", "a b  c")
```

```scala
// Scala
val pattern = """\d+""".r
val text = "abc123def456"

// Search
pattern.findFirstIn(text) match {
  case Some(m) => println(m)
  case None => ()
}

// Find all
val matches = pattern.findAllIn(text).toList

// Replace
val result = pattern.replaceAllIn(text, "X")

// Split
val parts = """\s+""".r.split("a b  c").toList

// Pattern matching with regex
val datePattern = """(\d{4})-(\d{2})-(\d{2})""".r
"2024-01-15" match {
  case datePattern(year, month, day) => s"$year/$month/$day"
  case _ => "no match"
}
```

## HTTP Requests

In dependency-free settings, prefer `java.net.http.HttpClient` (JDK 11+) or `java.net.HttpURLConnection`.
Use sttp only if dependencies are available.

```python
# Python
import requests

response = requests.get("https://api.example.com/data")
data = response.json()

response = requests.post(
    "https://api.example.com/data",
    json={"key": "value"},
    headers={"Authorization": "Bearer token"}
)
```

```scala
// Scala - sttp (recommended)
import sttp.client3._
import sttp.client3.circe._
import io.circe.generic.auto._

val backend = HttpURLConnectionBackend()

val response = basicRequest
  .get(uri"https://api.example.com/data")
  .send(backend)

val postResponse = basicRequest
  .post(uri"https://api.example.com/data")
  .body("""{"key": "value"}""")
  .header("Authorization", "Bearer token")
  .send(backend)
```

## Logging

In dependency-free settings, either:

- use `java.util.logging.Logger`, or
- keep logging minimal (e.g., `println`) if acceptable.

Use scala-logging / logback only when dependencies are available.

```python
# Python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

```scala
// Scala - scala-logging with logback
import com.typesafe.scalalogging.LazyLogging

class MyClass extends LazyLogging {
  logger.debug("Debug message")
  logger.info("Info message")
  logger.warn("Warning message")
  logger.error("Error message", exception)
}

// Alternative: slf4j directly
import org.slf4j.LoggerFactory

val logger = LoggerFactory.getLogger(getClass)
```

## Testing

In dependency-free settings, you may not have a test framework available; consider adding small self-checks in a `main` method (or REPL snippets) only if the task allows it.

```python
# Python - pytest
import pytest

def test_addition():
    assert 1 + 1 == 2

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_with_fixture(sample_data):
    assert sample_data["key"] == "value"

@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
])
def test_double(input, expected):
    assert input * 2 == expected
```

```scala
// Scala - ScalaTest
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class MySpec extends AnyFlatSpec with Matchers {
  "Addition" should "work" in {
    1 + 1 shouldEqual 2
  }

  it should "handle negative numbers" in {
    -1 + 1 shouldEqual 0
  }
}

// Table-driven tests
import org.scalatest.prop.TableDrivenPropertyChecks._

val examples = Table(
  ("input", "expected"),
  (1, 2),
  (2, 4)
)

forAll(examples) { (input, expected) =>
  input * 2 shouldEqual expected
}

// Scala - munit (simpler alternative)
class MySuite extends munit.FunSuite {
  test("addition") {
    assertEquals(1 + 1, 2)
  }
}
```

## Async/Concurrent Operations

```python
# Python
import asyncio

async def fetch_data(url: str) -> str:
    # async HTTP call
    await asyncio.sleep(1)
    return "data"

async def main():
    results = await asyncio.gather(
        fetch_data("url1"),
        fetch_data("url2"),
    )
```

```scala
// Scala - Future (standard)
import scala.concurrent.{Future, ExecutionContext}
import scala.concurrent.ExecutionContext.Implicits.global

def fetchData(url: String): Future[String] = Future {
  Thread.sleep(1000)
  "data"
}

val results: Future[List[String]] = Future.sequence(List(
  fetchData("url1"),
  fetchData("url2")
))

// cats-effect IO is great for FP, but requires dependencies.
// In dependency-free settings, stick to `Future`.
```

## Configuration

In dependency-free settings, prefer environment variables / simple argument parsing rather than adding a config library.

```python
# Python
import os
from dataclasses import dataclass

@dataclass
class Config:
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
```

```scala
// Scala - pureconfig
import pureconfig._
import pureconfig.generic.auto._

case class Config(dbHost: String, dbPort: Int)

val config = ConfigSource.default.loadOrThrow[Config]

// application.conf (HOCON format)
// db-host = "localhost"
// db-host = ${?DB_HOST}
// db-port = 5432
```

## Command Line Arguments

In dependency-free settings, parse `args: Array[String]` manually (small, explicit parsing) or use `java.util.Properties`/env vars.

```python
# Python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
parser.add_argument("--count", type=int, default=1)
args = parser.parse_args()
```

```scala
// Scala - scopt
import scopt.OParser

case class Config(name: String = "", count: Int = 1)

val builder = OParser.builder[Config]
val parser = {
  import builder._
  OParser.sequence(
    opt[String]("name").required().action((x, c) => c.copy(name = x)),
    opt[Int]("count").action((x, c) => c.copy(count = x))
  )
}

OParser.parse(parser, args, Config()) match {
  case Some(config) => // use config
  case None => // arguments are bad
}

// Scala - decline (FP style)
import com.monovore.decline._

val nameOpt = Opts.option[String]("name", "Name")
val countOpt = Opts.option[Int]("count", "Count").withDefault(1)

val command = Command("app", "Description") {
  (nameOpt, countOpt).tupled
}
```

## Build Tools Comparison

| Python | Scala |
|--------|-------|
| pip/poetry | sbt/mill |
| requirements.txt | build.sbt |
| pyproject.toml | build.sbt |
| setup.py | build.sbt |
| virtualenv | Project-local dependencies (automatic) |
