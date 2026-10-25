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


## Preserving a Required Public API When Translating

When a translation task lists required classes/functions (e.g., "must have TokenType, Token, BaseTokenizer, tokenize, toToken, withMetadata"), the verifier likely checks exact names and signatures. **Do not over-abstract.** Resist the urge to add sealed ADTs, type-class constraints, or helper traits that are not in the Python source.

### Rules

1. **Keep the required surface intact.** Preserve class and method names (camelCased: `tokenize_batch` → `tokenizeBatch`). Do not rename, split, or merge required entities. Do not add extra public types (e.g., `StringOrBytes`, `Temporal`, `Tokenizable`) unless the Python source defines them.

2. **Python union types → `Any` + pattern match, not new ADTs.** For `str | bytes`, `datetime | date`, `int | float`, prefer `Any` with a `match` block, or `Either[A, B]` when only two cases. Inventing `sealed trait StringOrBytes` changes the public API and breaks callers.

   ```scala
   // Python: def tokenize(value: str | bytes) -> Token
   def tokenize(value: Any): Token = value match {
     case s: String      => Token(s, TokenType.STRING)
     case b: Array[Byte] => Token(new String(b, "UTF-8"), TokenType.STRING)
     case other          => throw new IllegalArgumentException(s"Unsupported: $other")
   }
   ```

3. **Do not add generic type-class constraints the Python version lacks.** If Python has `class NumericTokenizer:` (non-generic), translate to a non-generic `class NumericTokenizer extends BaseTokenizer[Any]` that pattern-matches on `Int|Long|Double|...`. Do **not** write `class NumericTokenizer[A: Numeric]` — this changes the call sites.

4. **Translate Python `**kwargs` metadata to `Map[String, Any]` + varargs `withMetadata`.** This is the idiomatic replacement and matches the required method name.

   ```scala
   final case class Token(
     value: String,
     tokenType: TokenType,
     metadata: Map[String, Any] = Map.empty
   ) {
     def withMetadata(entries: (String, Any)*): Token =
       copy(metadata = metadata ++ entries)
   }
   ```

5. **Abstract base → `trait` with the same method names.** Use a `trait BaseTokenizer[A] { def tokenize(value: A): Token }` and provide a `toToken` helper on the companion or trait if the Python source has one. Subclasses `extends BaseTokenizer[A]` and `override def tokenize`.

### Worked Example: Tokenizer skeleton

```scala
sealed abstract class TokenType
object TokenType {
  case object STRING   extends TokenType
  case object NUMERIC  extends TokenType
  case object TEMPORAL extends TokenType
}

final case class Token(
  value: String,
  tokenType: TokenType,
  metadata: Map[String, Any] = Map.empty
) {
  def withMetadata(entries: (String, Any)*): Token =
    copy(metadata = metadata ++ entries)
}

trait BaseTokenizer[A] {
  def tokenize(value: A): Token
  def tokenizeBatch(values: IterableOnce[A]): Iterator[Token] =
    values.iterator.map(tokenize)
  protected def toToken(v: String, t: TokenType): Token = Token(v, t)
}

class StringTokenizer extends BaseTokenizer[String] {
  def tokenize(value: String): Token = toToken(value, TokenType.STRING)
}

// Non-generic: mirror Python's non-generic NumericTokenizer
class NumericTokenizer extends BaseTokenizer[Any] {
  def tokenize(value: Any): Token = value match {
    case n: Int    => toToken(n.toString, TokenType.NUMERIC)
    case n: Long   => toToken(n.toString, TokenType.NUMERIC)
    case n: Double => toToken(n.toString, TokenType.NUMERIC)
    case n: Float  => toToken(n.toString, TokenType.NUMERIC)
    case other     => throw new IllegalArgumentException(s"Not numeric: $other")
  }
}
```

### Checklist before finalizing a translation

- [ ] Every required class/function name appears, camelCased, at the top level.
- [ ] No extra public sealed traits/ADTs beyond what Python defines.
- [ ] No `[A: TypeClass]` constraints added to classes that were non-generic in Python.
- [ ] `withMetadata` takes `(String, Any)*` varargs and returns `Self` via `copy`.
- [ ] Union-typed parameters use `Any` + `match` (or `Either`), not new wrapper types.
