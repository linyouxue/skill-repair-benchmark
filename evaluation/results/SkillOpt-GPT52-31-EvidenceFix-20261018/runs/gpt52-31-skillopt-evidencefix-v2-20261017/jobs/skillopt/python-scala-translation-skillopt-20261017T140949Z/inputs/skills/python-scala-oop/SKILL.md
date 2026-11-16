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



## API Compatibility First

When translating Python OOP code for evaluators/tests, preserve the externally visible API before optimizing for Scala idioms.

Checklist:
- Preserve constructor parameter order and default values
- Preserve public method names expected by tests
- Keep inheritance relationships and override behavior intact
- Match mutability semantics (`var` vs immutable `val`)
- Preserve batch/helper functions exposed at module level
- Avoid renaming APIs only to sound “more Scala-like”

```python
# Python
class Config:
    def __init__(self, host="localhost", port=8080):
        self.host = host
        self.port = port
```

```scala
// Scala - preserve constructor defaults and field visibility
class Config(
  var host: String = "localhost",
  var port: Int = 8080
)
```

If Python callers mutate fields directly (`obj.name = ...`), use `var` or explicit setters instead of immutable-only translations.
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



Case classes are ideal for immutable Python dataclasses, but they can change runtime semantics.

Use case classes when the Python class is primarily:
- immutable data
- value equality based
- serialization friendly

Avoid replacing mutable/stateful Python classes with case classes if the original implementation:
- mutates fields after construction
- depends on reference identity
- exposes setter-style behavior
- stores internal caches or counters

```python
# Python
class Builder:
    def __init__(self):
        self.steps = []

    def add(self, step):
        self.steps.append(step)
```

```scala
// Scala - mutable builder semantics preserved
class Builder {
  private val steps = scala.collection.mutable.ListBuffer.empty[String]

  def add(step: String): Unit = {
    steps += step
  }
}
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



When Python subclasses override methods, Scala implementations should use `override` explicitly and preserve return types and side effects.

```python
# Python
class Counter:
    def increment(self):
        self.value += 1
```

```scala
// Scala - preserve mutation semantics
class Counter(var value: Int = 0) {
  def increment(): Unit = {
    value += 1
  }
}
```

Do not automatically convert mutable Python hierarchies into immutable case classes if tests expect object identity or in-place mutation.

For abstract base classes, preserve the inheritance contract:

```python
from abc import ABC, abstractmethod

class Tokenizer(ABC):
    @abstractmethod
    def tokenize(self, value):
        pass
```

```scala
abstract class Tokenizer {
  def tokenize(value: Any): Seq[String]
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



When translating Python `@classmethod` factories or module-level helper functions, companion objects are often the closest Scala equivalent.

```python
# Python
class User:
    @classmethod
    def from_name(cls, name):
        return cls(name.strip())
```

```scala
class User(val name: String)

object User {
  def fromName(name: String): User =
    new User(name.trim)
}
```

If evaluators expect names like `tokenizeBatch`, `toToken`, or `withMetadata`, expose those exact method names even if alternative Scala naming would be more idiomatic.
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
