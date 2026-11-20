---
name: python-scala-collections
description: Guide for translating Python collection operations to idiomatic Scala. Use when converting Python code that uses lists, dictionaries, sets, or involves collection transformations like map, filter, reduce, sorting, and aggregations.
---

# Python to Scala Collections Translation

## Collection Creation

### Lists

```python
# Python
empty = []
nums = [1, 2, 3]
repeated = [0] * 5
from_range = list(range(1, 11))
```

```scala
// Scala
val empty = List.empty[Int]  // or List[Int]()
val nums = List(1, 2, 3)
val repeated = List.fill(5)(0)
val fromRange = (1 to 10).toList
```

### Dictionaries → Maps

```python
# Python
empty = {}
person = {"name": "Alice", "age": 30}
from_pairs = dict([("a", 1), ("b", 2)])
```

```scala
// Scala
val empty = Map.empty[String, Int]
val person = Map("name" -> "Alice", "age" -> 30)
val fromPairs = List(("a", 1), ("b", 2)).toMap
```

### Sets

```python
# Python
empty = set()
nums = {1, 2, 3}
from_list = set([1, 2, 2, 3])
```

```scala
// Scala
val empty = Set.empty[Int]
val nums = Set(1, 2, 3)
val fromList = List(1, 2, 2, 3).toSet
```

## Transformation Operations

### Map

```python
# Python
doubled = [x * 2 for x in nums]
doubled = list(map(lambda x: x * 2, nums))
```

```scala
// Scala
val doubled = nums.map(_ * 2)
val doubled = nums.map(x => x * 2)
```

### Filter

```python
# Python
evens = [x for x in nums if x % 2 == 0]
evens = list(filter(lambda x: x % 2 == 0, nums))
```

```scala
// Scala
val evens = nums.filter(_ % 2 == 0)
val evens = nums.filter(x => x % 2 == 0)
```

### Reduce/Fold

```python
# Python
from functools import reduce
total = reduce(lambda a, b: a + b, nums)
total = sum(nums)
product = reduce(lambda a, b: a * b, nums, 1)
```

```scala
// Scala
val total = nums.reduce(_ + _)
val total = nums.sum
val product = nums.foldLeft(1)(_ * _)
// Use foldLeft when you need an initial value
```

### FlatMap

```python
# Python
nested = [[1, 2], [3, 4]]
flat = [x for sublist in nested for x in sublist]
```

```scala
// Scala
val nested = List(List(1, 2), List(3, 4))
val flat = nested.flatten
// or with transformation:
val flat = nested.flatMap(identity)
```

## Common Operations

### Length/Size

| Python | Scala |
|--------|-------|
| `len(lst)` | `lst.length` or `lst.size` |
| `len(dct)` | `map.size` |

### Access

| Python | Scala |
|--------|-------|
| `lst[0]` | `lst(0)` or `lst.head` |
| `lst[-1]` | `lst.last` |
| `lst[1:3]` | `lst.slice(1, 3)` |
| `lst[:3]` | `lst.take(3)` |
| `lst[3:]` | `lst.drop(3)` |
| `dct["key"]` | `map("key")` (throws if missing) |
| `dct.get("key")` | `map.get("key")` (returns Option) |
| `dct.get("key", default)` | `map.getOrElse("key", default)` |

### String Splitting Caveat

Python's `"  a  b ".split()` with **no argument** splits on runs of whitespace
and silently drops leading/trailing empty pieces. Scala's `String.split`
accepts a regex and returns empty leading/trailing tokens unless you filter
them out explicitly.

```python
# Python
"  hello world ".split()        # ["hello", "world"]
```

```scala
// Scala - mimic the Python default
"  hello world ".split("\\s+").filter(_.nonEmpty).toList
// List("hello", "world")

// Without the filter you get an empty leading element:
"  hello world ".split("\\s+").toList
// List("", "hello", "world")
```

When walking the original text to recover positions, call `indexOf` with a
cursor so repeated words resolve to the right offsets.

### Trimming Punctuation From Both Ends

Python's `str.strip(chars)` strips **both** ends against a character set in a
single call. Scala's `stripPrefix` / `stripSuffix` are string-based, not
character-set-based, so reach for `dropWhile` and `takeWhile`:

```python
# Python
word.strip(".,!?;:'\"()[]{}")
```

```scala
// Scala - works because Set[Char] implements Char => Boolean
val punctuation: Set[Char] = ".,!?;:'\"()[]{}".toSet

word.dropWhile(punctuation).reverse.dropWhile(punctuation).reverse
// equivalent, more direct:
word.dropWhile(punctuation).takeWhile(!punctuation(_))  // WRONG: drops middle chars
```

Only the first form (drop from both ends, keep the middle intact) mirrors
Python semantics. Avoid the double `reverse` chain's cost on hot paths —
prefer indexed scans if measured to matter.

### Membership

```python
# Python
if x in lst: ...
if key in dct: ...
```

```scala
// Scala
if (lst.contains(x)) ...
if (map.contains(key)) ...
```

### Concatenation

```python
# Python
combined = list1 + list2
merged = {**dict1, **dict2}
```

```scala
// Scala
val combined = list1 ++ list2
val merged = map1 ++ map2
```

### Sorting

```python
# Python
sorted_list = sorted(items)
sorted_desc = sorted(items, reverse=True)
sorted_by_key = sorted(items, key=lambda x: x.name)
items.sort()  # in-place
```

```scala
// Scala
val sortedList = items.sorted
val sortedDesc = items.sorted(Ordering[Int].reverse)
val sortedByKey = items.sortBy(_.name)
// Note: Scala collections are immutable by default, no in-place sort
```

### Grouping

```python
# Python
from itertools import groupby
from collections import defaultdict

# Group by key
grouped = defaultdict(list)
for item in items:
    grouped[item.category].append(item)
```

```scala
// Scala
val grouped = items.groupBy(_.category)
// Returns Map[Category, List[Item]]
```

### Aggregations

```python
# Python
total = sum(nums)
minimum = min(nums)
maximum = max(nums)
average = sum(nums) / len(nums)
```

```scala
// Scala
val total = nums.sum
val minimum = nums.min
val maximum = nums.max
val average = nums.sum.toDouble / nums.length
```

### Finding Elements

```python
# Python
first_even = next((x for x in nums if x % 2 == 0), None)
all_evens = all(x % 2 == 0 for x in nums)
any_even = any(x % 2 == 0 for x in nums)
```

```scala
// Scala
val firstEven = nums.find(_ % 2 == 0)  // Returns Option[Int]
val allEvens = nums.forall(_ % 2 == 0)
val anyEven = nums.exists(_ % 2 == 0)
```

### Zipping

```python
# Python
pairs = list(zip(list1, list2))
indexed = list(enumerate(items))
```

```scala
// Scala
val pairs = list1.zip(list2)
val indexed = items.zipWithIndex
```

## Dictionary/Map Operations

```python
# Python
keys = list(dct.keys())
values = list(dct.values())
items = list(dct.items())

for key, value in dct.items():
    process(key, value)

# Update
dct["new_key"] = value
updated = {**dct, "new_key": value}
```

```scala
// Scala
val keys = map.keys.toList
val values = map.values.toList
val items = map.toList  // List[(K, V)]

for ((key, value) <- map) {
  process(key, value)
}

// Update (creates new map, immutable)
val updated = map + ("new_key" -> value)
val updated = map.updated("new_key", value)
```

## Mutable vs Immutable

Python collections are mutable by default. Scala defaults to immutable.

```python
# Python - mutable
lst.append(4)
lst.extend([5, 6])
dct["key"] = value
```

```scala
// Scala - immutable (creates new collection)
val newList = lst :+ 4
val newList = lst ++ List(5, 6)
val newMap = map + ("key" -> value)

// Scala - mutable (when needed)
import scala.collection.mutable
val mutableList = mutable.ListBuffer(1, 2, 3)
mutableList += 4
mutableList ++= List(5, 6)
```

### When the Python API is Explicitly Mutable, Keep It Mutable

If a Python class exposes `.append` / `.add` / `.clear` through its public
surface — e.g. a batch-like holder with an internal `list[...]` plus a flag
that only flips from `False` to `True` — that mutability is part of the
contract. Translating it to an immutable Scala case class whose updates
return a new instance silently breaks any caller that called the old method
for its side effect.

```scala
// Prefer mutable collection + var flag, exposing identical method names.
class Batch[A] {
  private val _items  = scala.collection.mutable.ListBuffer.empty[A]
  private var _closed = false

  def items: List[A]    = _items.toList
  def closed: Boolean   = _closed

  def add(item: A): Unit = {
    if (_closed) throw new IllegalStateException("Batch already closed")
    _items += item
  }

  def close(): Unit = _closed = true
}
```

The immutable version — e.g. `copy(items = items :+ x)` returning a new
instance — may compile, but anything the caller did previously by chaining
`b.add(x); b.add(y)` will silently drop the appended items.

## enum type

Use UPPERCASE for enum and constant names in Scala (same as in Python) E.g.

```python
class TokenType(Enum):
    STRING = "string"
    NUMERIC = "numeric"
    TEMPORAL = "temporal"
    STRUCTURED = "structured"
    BINARY = "binary"
    NULL = "null"
```

```scala
sealed abstract class BaseType(val value: String)
object BaseType {
  case object STRING     extends BaseType("string")
  case object NUMERIC    extends BaseType("numeric")
  case object TEMPORAL   extends BaseType("temporal")
  case object STRUCTURED extends BaseType("structured")
  case object BINARY     extends BaseType("binary")
  case object NULL       extends BaseType("null")

  val values: Seq[BaseType] =
    Seq(STRING, NUMERIC, TEMPORAL, STRUCTURED, BINARY, NULL)
}
```

Do not use PascalCase. E.g. the following is against the principle:

```scala
object BaseType {
  case object String extends BaseType { val value = "string" }
}
```

Key points for this encoding:

- Declare the sealed parent as `sealed abstract class X(val value: String)`
  so each case object can pass its payload through the constructor, matching
  Python's `Enum` `.value` attribute.
- Include **every** variant from the Python enum — translating partial sets
  (e.g., dropping `NULL`) silently changes behaviour when a dispatcher reaches
  the default branch.
- Keep `values: Seq[T]` if the Python code relies on `list(TokenType)` or
  similar iteration.
