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
object BaseType {
  case object STRING extends BaseType { val value = "string" }
  case object NUMERIC extends BaseType { val value = "numeric" }
  case object TEMPORAL extends BaseType { val value = "temporal" }
  case object STRUCTURED extends BaseType { val value = "structured" }
  case object BINARY extends BaseType { val value = "binary" }
}
```

Do not use PascalCase. E.g. the following is against the principle:

```scala
object BaseType {
  case object String extends BaseType { val value = "string" }
}
```



## Scala 2.13 Tokenizer and Batch Collection Patterns

Tokenizer code should make collection shape and evaluation strategy explicit. Prefer `List` when preserving Python list semantics is the API contract, `Vector` for indexed or batch-oriented results, `Seq` only when the implementation does not require a concrete representation, and `Map` only when key uniqueness is intended.

```scala
// Explicit signatures prevent Scala 2.13 inference from selecting an
// incompatible collection type.
def tokenizeOne(input: String): List[Token] = {
  // produce tokens in source order
  List.empty[Token]
}

def tokenizeBatch(inputs: List[String]): List[Token] =
  inputs.flatMap(tokenizeOne) // preserves row order and token order

// Keep row boundaries when the caller needs to distinguish each input.
def tokenizeBatchByInput(inputs: Vector[String]): Vector[List[Token]] =
  inputs.map(input => tokenizeOne(input))
```

`flatMap` is the direct equivalent of flattening a Python list of token lists. It preserves duplicates and returns an empty result for an empty batch. Do not replace it with `toSet`, a map keyed by token text, or an unordered aggregation when repeated tokens or repeated metadata are meaningful.

```scala
val emptyBatch: List[Token] = List.empty[Token]
val flattened: Vector[Token] =
  batchResults.iterator.flatMap(identity).toVector // materialize once, in order

// Use foldLeft rather than reduce when the input may be empty.
val allTokens: List[Token] =
  batchResults.foldLeft(List.empty[Token])(_ ++ _)
```

Use an occurrence sequence for metadata when duplicate keys or duplicate metadata records must survive translation. A `Map` silently replaces an earlier value for the same key.

```scala
// Duplicate metadata entries remain distinct and retain insertion order.
type Metadata = List[(String, String)]
type TokenResult = (Token, Metadata)

val results: Vector[TokenResult] =
  rawResults.map { case (token, metadata) =>
    (token, metadata.toList)
  }
```

Choose strict conversions deliberately. `Iterator` is one-shot, and `view`/`mapValues` can be lazy; materialize at the tokenizer boundary when the returned value is expected to behave like a Python list or dictionary.

```scala
val strictTokens: List[Token] = tokenIterator.toList
val strictTokensVector: Vector[Token] = tokenIterator.toVector
val strictMap: Map[String, Vector[Token]] =
  tokenGroups.view.mapValues(_.toVector).toMap
```

For accumulation, immutable builders avoid repeated concatenation and make the result type explicit.

```scala
val tokenBuilder: Vector.newBuilder[Token] = Vector.newBuilder[Token]
inputs.foreach { input =>
  tokenBuilder ++= tokenizeOne(input)
}
val tokens: Vector[Token] = tokenBuilder.result()

val metadataBuilder: Map.newBuilder[String, String] = Map.newBuilder
metadataBuilder += ("source" -> "tokenizer")
val metadata: Map[String, String] = metadataBuilder.result()
```

`Map` is appropriate for unique lookup keys, but do not use it to represent an ordered Python dictionary when output order is observable. Keep ordered entries as `List[(K, V)]` or `Vector[(K, V)]`; use `ListMap` only when a map API and deterministic insertion order are both required. Likewise, `groupBy` preserves the order of values within each group, but callers should not rely on ordinary `Map` key iteration order.

```scala
val byCategory: Map[Category, Vector[Token]] =
  tokens.groupBy(_.category).view.mapValues(_.toVector).toMap

// First-seen group order and within-group order are explicit here.
def stableGroupBy[A, K](items: Vector[A], keyOf: A => K):
    Vector[(K, Vector[A])] =
  items.foldLeft(Vector.empty[(K, Vector[A])]) { (groups, item) =>
    val key = keyOf(item)
    groups.indexWhere(_._1 == key) match {
      case -1 => groups :+ (key, Vector(item))
      case i  => groups.updated(i, (key, groups(i)._2 :+ item))
    }
  }
```

Apply deduplication only at the stage where it is semantically intended. `distinct`/`distinctBy` preserve the first occurrence in a strict sequence, but deduplicating complete token-and-metadata results can remove occurrences that Python would retain. If metadata belongs to each occurrence, flatten and attach it without deduplicating; if only token identity is deduplicated, do that explicitly before attaching occurrence metadata.

```scala
val uniqueTokens: Vector[Token] = tokens.distinct
val uniqueByIdentity: Vector[Token] = tokens.distinctBy(token => token.identity)
```

Handle tokenizer boundaries explicitly: empty input should produce an empty token collection unless the Python implementation emits a boundary token, and empty strings inside a nonempty batch must not be dropped accidentally. Use `Option` or a documented boundary representation for missing values rather than indexing with `head` or `apply(0)` without checking.
