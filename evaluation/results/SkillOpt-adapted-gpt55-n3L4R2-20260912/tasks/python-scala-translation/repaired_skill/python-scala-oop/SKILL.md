---
name: python-scala-oop
description: Guide for translating Python classes, inheritance, and object-oriented patterns to Scala. Use when converting Python code with classes, dataclasses, abstract classes, inheritance, properties, static methods, class methods, or design patterns.
---

# Python to Scala OOP Translation

## Basic Classes

```python
# Python
class Person:
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age

    def greet(self) -> str:
        return f"Hello, I'm {self.name}"
```

```scala
// Scala
class Person(val name: String, val age: Int) {
  def greet: String = s"Hello, I'm $name"
}

// Usage
val person = new Person("Alice", 30)  // 'new' required for class
```

## Data Classes → Case Classes

```python
# Python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

@dataclass(frozen=True)
class ImmutablePoint:
    x: float
    y: float
```

```scala
// Scala - case class is idiomatic
case class Point(x: Double, y: Double)

// Case classes are immutable by default
// They auto-generate: equals, hashCode, toString, copy, apply

// Usage
val p = Point(1.0, 2.0)  // No 'new' needed for case class
val p2 = p.copy(x = 3.0)  // Creates new instance with x changed
```

## Properties

```python
# Python
class Circle:
    def __init__(self, radius: float):
        self._radius = radius

    @property
    def radius(self) -> float:
        return self._radius

    @radius.setter
    def radius(self, value: float):
        if value < 0:
            raise ValueError("Radius must be non-negative")
        self._radius = value

    @property
    def area(self) -> float:
        return 3.14159 * self._radius ** 2
```

```scala
// Scala
class Circle(private var _radius: Double) {
  require(_radius >= 0, "Radius must be non-negative")

  def radius: Double = _radius

  def radius_=(value: Double): Unit = {
    require(value >= 0, "Radius must be non-negative")
    _radius = value
  }

  def area: Double = math.Pi * _radius * _radius
}

// Idiomatic Scala: prefer immutable case class
case class Circle(radius: Double) {
  require(radius >= 0, "Radius must be non-negative")
  def area: Double = math.Pi * radius * radius
}
```

## Inheritance

```python
# Python
class Animal:
    def __init__(self, name: str):
        self.name = name

    def speak(self) -> str:
        raise NotImplementedError

class Dog(Animal):
    def speak(self) -> str:
        return f"{self.name} says woof!"

class Cat(Animal):
    def speak(self) -> str:
        return f"{self.name} says meow!"
```

```scala
// Scala
abstract class Animal(val name: String) {
  def speak: String  // Abstract method
}

class Dog(name: String) extends Animal(name) {
  override def speak: String = s"$name says woof!"
}

class Cat(name: String) extends Animal(name) {
  override def speak: String = s"$name says meow!"
}
```

## Abstract Classes and Interfaces

```python
# Python
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self) -> float:
        pass

    @abstractmethod
    def perimeter(self) -> float:
        pass

    def describe(self) -> str:
        return f"Area: {self.area()}, Perimeter: {self.perimeter()}"
```

```scala
// Scala - abstract class
abstract class Shape {
  def area: Double
  def perimeter: Double
  def describe: String = s"Area: $area, Perimeter: $perimeter"
}

// Scala - trait (preferred for interfaces)
trait Shape {
  def area: Double
  def perimeter: Double
  def describe: String = s"Area: $area, Perimeter: $perimeter"
}

// Implementation
case class Rectangle(width: Double, height: Double) extends Shape {
  def area: Double = width * height
  def perimeter: Double = 2 * (width + height)
}
```

## Multiple Inheritance → Traits

```python
# Python
class Flyable:
    def fly(self) -> str:
        return "Flying!"

class Swimmable:
    def swim(self) -> str:
        return "Swimming!"

class Duck(Animal, Flyable, Swimmable):
    def speak(self) -> str:
        return "Quack!"
```

```scala
// Scala - use traits for mixins
trait Flyable {
  def fly: String = "Flying!"
}

trait Swimmable {
  def swim: String = "Swimming!"
}

class Duck(name: String) extends Animal(name) with Flyable with Swimmable {
  override def speak: String = "Quack!"
}
```

## Static Methods and Class Methods

```python
# Python
class MathUtils:
    PI = 3.14159

    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b

    @classmethod
    def from_string(cls, s: str) -> "MathUtils":
        return cls()
```

```scala
// Scala - use companion object
class MathUtils {
  // Instance methods here
}

object MathUtils {
  val PI: Double = 3.14159

  def add(a: Int, b: Int): Int = a + b

  def fromString(s: String): MathUtils = new MathUtils()
}

// Usage
MathUtils.add(1, 2)
MathUtils.PI
```

## Factory Pattern

```python
# Python
class Shape:
    @staticmethod
    def create(shape_type: str) -> "Shape":
        if shape_type == "circle":
            return Circle()
        elif shape_type == "rectangle":
            return Rectangle()
        raise ValueError(f"Unknown shape: {shape_type}")
```

```scala
// Scala - companion object with apply
sealed trait Shape

case class Circle(radius: Double) extends Shape
case class Rectangle(width: Double, height: Double) extends Shape

object Shape {
  def apply(shapeType: String): Shape = shapeType match {
    case "circle" => Circle(1.0)
    case "rectangle" => Rectangle(1.0, 1.0)
    case other => throw new IllegalArgumentException(s"Unknown shape: $other")
  }
}

// Usage
val shape = Shape("circle")
```

## Enums

```python
# Python
from enum import Enum, auto

class Color(Enum):
    RED = auto()
    GREEN = auto()
    BLUE = auto()

class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
```

```scala
// Scala 3
enum Color:
  case Red, Green, Blue

enum Status(val value: String):
  case Pending extends Status("pending")
  case Approved extends Status("approved")
  case Rejected extends Status("rejected")

// Scala 2 - sealed trait pattern
sealed trait Color
object Color {
  case object Red extends Color
  case object Green extends Color
  case object Blue extends Color
}
```

## Singleton

```python
# Python
class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

```scala
// Scala - object is a singleton
object Singleton {
  def doSomething(): Unit = println("I'm a singleton!")
}

// Usage
Singleton.doSomething()
```

## Special Methods (Dunder Methods)

| Python | Scala |
|--------|-------|
| `__init__` | Primary constructor |
| `__str__` | `toString` |
| `__repr__` | `toString` (case classes auto-generate) |
| `__eq__` | `equals` (case classes auto-generate) |
| `__hash__` | `hashCode` (case classes auto-generate) |
| `__len__` | `length` or `size` method |
| `__getitem__` | `apply` method |
| `__setitem__` | `update` method |
| `__iter__` | Extend `Iterable` trait |
| `__add__` | `+` method |
| `__lt__`, `__le__`, etc. | Extend `Ordered` trait |

```python
# Python
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)

    def __str__(self):
        return f"Vector({self.x}, {self.y})"
```

```scala
// Scala
case class Vector(x: Double, y: Double) {
  def +(other: Vector): Vector = Vector(x + other.x, y + other.y)
  // toString auto-generated by case class
}
```


## Scala 2.13 Tokenizer Hierarchy Pattern

For tokenizer translations, first copy the Python API's exact class names, method names, parameter types, return types, defaults, and visibility requirements. Then apply Scala's modeling conventions without changing the externally tested contract.

Use immutable case classes for token data and configuration data. Preserve every Python field, including metadata, rather than replacing the source model with an unrelated representation. For example:

```scala
// Adapt fields and types to the source Python code.
final case class Token(
  value: String,
  tokenType: TokenType,
  metadata: Map[String, String] = Map.empty
) {
  def withMetadata(entries: Map[String, String]): Token =
    copy(metadata = metadata ++ entries)
}
```

In Scala 2.13, model a closed token-type hierarchy with a sealed trait and case objects/case classes when exhaustive pattern matching is useful. Use the source's actual token names and payloads:

```scala
sealed trait TokenType
object TokenType {
  case object StringType extends TokenType
  case object NumericType extends TokenType
  case object TemporalType extends TokenType
  case object WhitespaceType extends TokenType
  // Add every source token type; do not silently omit variants.
}
```

Represent the common tokenizer behavior with an abstract class or trait. Abstract members must be explicit, and every implementation of an inherited concrete or abstract member must use `override`:

```scala
abstract class BaseTokenizer {
  def tokenize(input: String): Seq[Token]

  def tokenizeBatch(inputs: Seq[String]): Seq[Seq[Token]] =
    inputs.map(tokenize)

  def toToken(value: String, tokenType: TokenType): Token =
    Token(value, tokenType)
}

final class StringTokenizer extends BaseTokenizer {
  override def tokenize(input: String): Seq[Token] = {
    // Preserve the Python algorithm and edge-case behavior here.
    Seq(toToken(input, TokenType.StringType))
  }
}

final class NumericTokenizer extends BaseTokenizer {
  override def tokenize(input: String): Seq[Token] = {
    // Translate the Python numeric recognition rules exactly.
    Seq(toToken(input, TokenType.NumericType))
  }
}

final class TemporalTokenizer extends BaseTokenizer {
  override def tokenize(input: String): Seq[Token] = {
    // Translate the Python temporal recognition rules exactly.
    Seq(toToken(input, TokenType.TemporalType))
  }
}

final class WhitespaceTokenizer extends BaseTokenizer {
  override def tokenize(input: String): Seq[Token] =
    input.split("\\s+").iterator.filter(_.nonEmpty).map { part =>
      toToken(part, TokenType.WhitespaceType)
    }.toSeq
}

final class UniversalTokenizer(
    delegates: Seq[BaseTokenizer]
) extends BaseTokenizer {
  override def tokenize(input: String): Seq[Token] =
    delegates.iterator.flatMap(_.tokenize(input)).toSeq
}
```

If the Python hierarchy requires constructor arguments or protected/private state, reproduce those arguments in the Scala primary constructors and use `private`/`protected` deliberately. Do not make members public merely to simplify translation. If a Python method is a class method or static method, place the corresponding factory or utility in the companion object; use `apply` only when it is compatible with the required public API:

```scala
object UniversalTokenizer {
  def apply(): UniversalTokenizer =
    new UniversalTokenizer(
      Seq(new StringTokenizer, new NumericTokenizer, new TemporalTokenizer)
    )
}
```

Translate a mutable Python builder into an immutable or fluent builder whose methods return a new builder, while retaining the required `TokenizerBuilder` name and all required operations:

```scala
final case class TokenizerBuilder(
    tokenizers: Seq[BaseTokenizer] = Seq.empty
) {
  def add(tokenizer: BaseTokenizer): TokenizerBuilder =
    copy(tokenizers = tokenizers :+ tokenizer)

  def build(): UniversalTokenizer =
    new UniversalTokenizer(tokenizers)
}

object TokenizerBuilder {
  def apply(): TokenizerBuilder = new TokenizerBuilder()
}
```

The snippets are structural patterns, not permission to invent behavior: replace illustrative fields, token variants, constructors, defaults, and recognition logic with the exact behavior of the Python source. Preserve dispatch order, exception behavior, empty-input behavior, batch behavior, and metadata semantics.



## Translation Contract Checklist for Tokenizer APIs

Before compiling, verify that the Scala file still exposes every mandated class and function from the Python source: `TokenType`, `Token`, `BaseTokenizer`, `StringTokenizer`, `NumericTokenizer`, `TemporalTokenizer`, `UniversalTokenizer`, `WhitespaceTokenizer`, `TokenizerBuilder`, `tokenize`, `tokenizeBatch`, `toToken`, and `withMetadata`. Keep public names and signatures compatible with the tests; Scala naming conventions must not rename an externally required method.

Use these mappings deliberately:

- Python `__init__` becomes the Scala primary or auxiliary constructor; preserve required defaults and construction compatibility.
- Python instance methods remain instance methods; inherited implementations are explicitly marked `override`.
- Python `@staticmethod` becomes a companion-object method or another explicitly public utility with the required call shape.
- Python `@classmethod` becomes a companion-object factory that constructs the concrete or requested subtype rather than hard-coding an incompatible subtype.
- Python properties become parameter accessors, computed `def` methods, or validated setters; preserve whether callers can read or mutate them.
- Python inheritance and dynamic dispatch become `extends`/`with` relationships and overridden methods; test calls through `BaseTokenizer` references, not only concrete references.
- Python optional values and absent metadata should use `Option` or an immutable collection only when this preserves the source's observable behavior.
- Compile with Scala 2.13, and check both direct construction and companion-object construction where the Python API permits them.
