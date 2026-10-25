---
name: python-scala-libraries
description: Guide for mapping common Python libraries and idioms to Scala equivalents. Use when converting Python code that uses standard library modules (json, datetime, os, re, logging) or needs equivalent Scala libraries for HTTP, testing, or async operations.
---

# Python to Scala Library Mappings

## JSON Handling

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
// Scala - circe (most popular)
import io.circe._
import io.circe.generic.auto._
import io.circe.syntax._
import io.circe.parser._

case class Person(name: String, age: Int)

val person = Person("Alice", 30)
val jsonStr: String = person.asJson.noSpaces
val parsed: Either[Error, Person] = decode[Person](jsonStr)

// Scala - play-json
import play.api.libs.json._

case class Person(name: String, age: Int)
implicit val personFormat: Format[Person] = Json.format[Person]

val json = Json.toJson(person)
val parsed = json.as[Person]
```

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
val formatted = now.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
val parsed = LocalDate.parse("2024-01-15")
val tomorrow = now.plusDays(1)

// Timezone
val utcNow = ZonedDateTime.now(ZoneOffset.UTC)
val instant = Instant.now()
```


### strftime → DateTimeFormatter (NOT identical — must translate)

Python's `strftime`/`strptime` format codes are **different** from Java's `DateTimeFormatter` patterns. A direct pass-through will silently produce wrong output. Translate codes explicitly:

| Python `strftime` | Java `DateTimeFormatter` | Meaning |
|---|---|---|
| `%Y` | `yyyy` | 4-digit year |
| `%y` | `yy`   | 2-digit year |
| `%m` | `MM`   | month (01-12) |
| `%d` | `dd`   | day of month |
| `%H` | `HH`   | hour (00-23) |
| `%I` | `hh`   | hour (01-12) |
| `%M` | `mm`   | minute |
| `%S` | `ss`   | second |
| `%f` | `SSSSSS` | microseconds (6 digits) |
| `%p` | `a`    | AM/PM |
| `%j` | `DDD`  | day of year |
| `%A` | `EEEE` | full weekday name |
| `%a` | `EEE`  | short weekday name |
| `%B` | `MMMM` | full month name |
| `%b` | `MMM`  | short month name |
| `%Z` | `zzz`  | timezone name |
| `%z` | `Z`    | timezone offset |
| `%%` | `%`    | literal percent |

Provide a helper when translating code that accepts user-supplied format strings:

```scala
def pythonFormatToJava(fmt: String): String = {
  val mapping = Seq(
    "%Y" -> "yyyy", "%y" -> "yy",
    "%m" -> "MM",   "%d" -> "dd",
    "%H" -> "HH",   "%I" -> "hh",
    "%M" -> "mm",   "%S" -> "ss",
    "%f" -> "SSSSSS",
    "%p" -> "a",    "%j" -> "DDD",
    "%A" -> "EEEE", "%a" -> "EEE",
    "%B" -> "MMMM", "%b" -> "MMM",
    "%Z" -> "zzz",  "%z" -> "Z",
    "%%" -> "%"
  )
  // Quote literal text that DateTimeFormatter would otherwise interpret.
  // Simple approach: replace tokens in order; wrap non-% letters in single quotes if needed.
  mapping.foldLeft(fmt) { case (acc, (py, java)) => acc.replace(py, java) }
}
```

### Dispatching on `datetime | date` (order matters)

In Python, `datetime` is a subclass of `date`, so `isinstance(x, datetime)` must be checked **before** `isinstance(x, date)`. In Scala/`java.time`, `LocalDateTime` and `LocalDate` are unrelated types, but when matching on `Any` always put the more specific case first:

```scala
value match {
  case dt: LocalDateTime => /* datetime branch */
  case d:  LocalDate     => /* date branch */
  case _                 => /* fallback */
}
```

### Bytes decoding

Python's `bytes.decode('utf-8')` → Scala:

```scala
import java.nio.charset.StandardCharsets
val s: String = new String(bytes, StandardCharsets.UTF_8)
```

Do **not** use `bytes.map(_.toChar).mkString` (breaks multibyte UTF-8) or `new String(bytes)` (uses platform default charset).

### f-string formatting

| Python | Scala |
|---|---|
| `f"{x}"` | `s"$x"` |
| `f"{x:.2f}"` | `f"$x%.2f"` (note: `f` interpolator, not `s`) |
| `f"{x:>5}"` | `f"$x%5s"` |
| `f"{x:05d}"` | `f"$x%05d"` |
| `f"{x:.3e}"` | `f"$x%.3e"` |

The `f` interpolator uses `java.util.Formatter` syntax (same as `String.format`), which differs from Python's format spec but covers the common cases above.

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

// Scala - cats-effect IO (preferred for FP)
import cats.effect.IO
import cats.syntax.parallel._

def fetchData(url: String): IO[String] = IO.sleep(1.second) *> IO.pure("data")

val results: IO[List[String]] = List(
  fetchData("url1"),
  fetchData("url2")
).parSequence
```

## Configuration

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
