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



## Scala 2.13 Tokenizer-Hierarchy Recipe

For a Python tokenizer module containing `TokenType`, `Token`, `BaseTokenizer`, `StringTokenizer`, `NumericTokenizer`, `TemporalTokenizer`, `UniversalTokenizer`, `WhitespaceTokenizer`, `TokenizerBuilder`, `tokenize`, `tokenizeBatch`, `toToken`, and `withMetadata`, preserve every public name and operation required by the source and tests. First inventory the exact Python constructor parameters, defaults, attributes, return types, validation, and dispatch rules; do not replace a required API with a merely idiomatic alternative.

### Token categories and immutable records

Use Scala 2.13 syntax only. Represent a closed token category hierarchy with a sealed trait and case objects (or a sealed abstract class when categories carry data):

```scala
sealed trait TokenType
object TokenType {
  case object StringToken extends TokenType
  case object NumericToken extends TokenType
  case object TemporalToken extends TokenType
  case object WhitespaceToken extends TokenType
  case object UnknownToken extends TokenType
}
```

Use immutable case classes for the Python token/dataclass records. Copy the source field names and field order exactly when those are public; use concrete types rather than `Any`, and use `Option[T]` only when the Python API permits absence. Keep metadata immutable, for example `Map[String, String]` or a dedicated immutable metadata case class if the source has a fixed schema:

```scala
final case class Token(
  value: String,
  tokenType: TokenType,
  metadata: Map[String, String] = Map.empty
) {
  def withMetadata(extra: Map[String, String]): Token =
    copy(metadata = metadata ++ extra)

  def toToken: Token = this
}
```

The example fields are a pattern, not permission to invent fields: translate the actual Python record and preserve the required `toToken` and `withMetadata` signatures and semantics. Put validation in the case-class body with `require` only when the Python constructor validates the same invariant.

### Base class and concrete tokenizers

Model `BaseTokenizer` as a trait when it has no constructor state, or as an abstract class when the Python base constructor has state. Declare abstract operations without implementations and mark every implementation with `override`:

```scala
abstract class BaseTokenizer {
  def tokenize(input: String): Seq[Token]

  def tokenizeBatch(inputs: Seq[String]): Seq[Seq[Token]] =
    inputs.map(tokenize)
}

final class StringTokenizer(/* exact Python constructor parameters */)
    extends BaseTokenizer {
  override def tokenize(input: String): Seq[Token] = {
    // Preserve the Python implementation's classification and output behavior.
    ???
  }
}
```

Translate each required concrete subclass separately: `StringTokenizer`, `NumericTokenizer`, `TemporalTokenizer`, and `WhitespaceTokenizer`. Give each the same externally usable constructor parameters and defaults as Python, using Scala default arguments where appropriate. If Python subclasses rely on inherited state, pass it explicitly to `extends BaseTokenizer(...)`; do not silently remove it. If a Python method overrides a base method, use the identical compatible Scala parameter and result types plus `override`.

`UniversalTokenizer` should compose or dispatch to the concrete tokenizers according to the Python source. Prefer a typed collection such as `Seq[BaseTokenizer]` or explicit fields; do not use `Any` or reflection. Preserve the source's precedence when multiple tokenizers can recognize the same input, and preserve whether unmatched input yields an empty result, an unknown token, or an exception.

### Companion objects and builder

Map Python `@staticmethod` and `@classmethod` behavior to a companion object while retaining the required callable operation names. A factory should return the declared base type and validate unknown choices in the same way as Python:

```scala
object UniversalTokenizer {
  def apply(/* exact source parameters */): UniversalTokenizer =
    new UniversalTokenizer(/* matching arguments */)
}
```

Implement `TokenizerBuilder` with immutable state by returning a new builder from configuration methods, unless the Python API explicitly requires mutation. Keep `build()` returning the required tokenizer type and preserve defaults, registration order, duplicate handling, and validation:

```scala
final case class TokenizerBuilder(
    /* exact immutable configuration fields and defaults */
) {
  def withStringTokenizer(/* exact parameters */): TokenizerBuilder =
    copy(/* updated fields */)

  def build(): BaseTokenizer =
    new UniversalTokenizer(/* resolved configuration */)
}
```

If callers must use `new TokenizerBuilder(...)` rather than a case-class factory, use a normal class with the same constructor and provide a companion `apply` only as an additional convenience. Do not rename required Python methods to Scala-only alternatives; a Scala-friendly alias may be added only in addition to the required API.

### Python feature mapping and compile checks

Map public Python attributes to `val` constructor parameters, read/write properties to methods (and `_=`, only when mutation is required), class/static methods to companion-object methods, and Python exceptions to specific Scala exceptions such as `IllegalArgumentException` or `NoSuchElementException` according to the source behavior. Use `Option`, `Either`, or a documented exception only where it remains compatible with the required public API. Keep helper operations such as `toToken` and `withMetadata` available on the same public type expected by callers.

Before finishing, compile with Scala 2.13 and check construction through every required constructor/default, calls to every required method, subtype assignments through `BaseTokenizer`, pattern matches over `TokenType`, batch processing, metadata updates, and invalid-input paths. Avoid Scala 3 enums, significant indentation syntax, opaque types, and other Scala 3-only constructs.
