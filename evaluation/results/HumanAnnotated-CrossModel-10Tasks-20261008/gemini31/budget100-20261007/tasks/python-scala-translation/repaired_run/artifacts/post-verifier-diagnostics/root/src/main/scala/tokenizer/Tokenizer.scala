package tokenizer

import io.circe.Json
import io.circe.syntax._

import java.time.{LocalDate, LocalDateTime}
import java.time.format.DateTimeFormatter
import scala.collection.mutable
import scala.util.Try

// ============================================================================
// Protocol definitions (structural typing)
// ============================================================================

trait Tokenizable {
  def toToken: String
}

trait HasLength {
  def length: Int
}

trait TokenProcessor[-T] {
  def process(item: T): Unit
}

// ============================================================================
// Enums and Constants
// ============================================================================

sealed abstract class TokenType(val value: String)
object TokenType {
  case object STRING extends TokenType("string")
  case object NUMERIC extends TokenType("numeric")
  case object TEMPORAL extends TokenType("temporal")
  case object STRUCTURED extends TokenType("structured")
  case object BINARY extends TokenType("binary")
  case object NULL extends TokenType("null")
}

// ============================================================================
// Core Token Classes
// ============================================================================

case class Token(
    value: String,
    tokenType: TokenType,
    metadata: Map[String, Any] = Map.empty
) {
  def withMetadata(kwargs: (String, Any)*): Token = {
    copy(metadata = metadata ++ kwargs.toMap)
  }
}

class MutableTokenBatch(
    private var _tokens: List[Token] = Nil,
    private var _processed: Boolean = false
) {
  def tokens: List[Token] = _tokens

  def add(token: Token): Unit = {
    if (_processed) {
      throw new RuntimeException("Batch already processed")
    }
    _tokens = _tokens :+ token
  }

  def markProcessed(): Unit = {
    _processed = true
  }
}

// ============================================================================
// Generic Container Classes
// ============================================================================

class TokenContainer[+T](items: Seq[T]) {
  private val _items: Vector[T] = items.toVector

  def getAll: Vector[T] = _items
  
  def size: Int = _items.size

  def mapTokens(func: T => String): List[String] = {
    _items.map(func).toList
  }
}

class TokenSink[-T] {
  private val _received: mutable.ListBuffer[Any] = mutable.ListBuffer.empty

  def receive(item: T): Unit = {
    _received += item
  }

  def drain(): List[Any] = {
    val result = _received.toList
    _received.clear()
    result
  }
}

class BivariantHandler[T](default: T) {
  private var _value: T = default

  def get(): T = _value

  def set(value: T): Unit = {
    _value = value
  }

  def transform(func: T => T): T = {
    _value = func(_value)
    _value
  }
}

// ============================================================================
// Tokenizer Implementations
// ============================================================================

trait BaseTokenizer[T] {
  def tokenize(value: T): Token

  def tokenizeBatch(values: Iterable[T]): Iterator[Token] = {
    values.iterator.map(tokenize)
  }
}

class StringTokenizer(
    encoding: String = "utf-8",
    normalizer: String => String = identity
) extends BaseTokenizer[Either[String, Array[Byte]]] {

  def tokenize(value: Either[String, Array[Byte]]): Token = {
    val strValue = value match {
      case Left(s) => s
      case Right(b) => new String(b, encoding)
    }

    val normalized = normalizer(strValue)
    Token(normalized, TokenType.STRING)
  }
}

class NumericTokenizer(
    precision: Int = 6,
    formatOptions: Map[String, Any] = Map.empty
) extends BaseTokenizer[AnyVal] { // Scala numeric types are AnyVal

  def tokenize(value: AnyVal): Token = {
    val strValue = value match {
      case d: Double => s"%.${precision}f".format(d)
      case f: Float  => s"%.${precision}f".format(f)
      case b: BigDecimal => s"%.${precision}f".format(b)
      case other => other.toString
    }

    Token(
      strValue,
      TokenType.NUMERIC,
      Map("original_type" -> value.getClass.getSimpleName)
    )
  }
}

class TemporalTokenizer(
    formatStr: Option[String] = None
) extends BaseTokenizer[Either[LocalDateTime, LocalDate]] {

  private val ISO_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")
  private val DATE_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd")

  def tokenize(value: Either[LocalDateTime, LocalDate]): Token = {
    val formatter = formatStr match {
      case Some(fmt) => DateTimeFormatter.ofPattern(fmt)
      case None =>
        value match {
          case Left(_) => ISO_FORMAT
          case Right(_) => DATE_FORMAT
        }
    }

    val strValue = value match {
      case Left(dt) => dt.format(formatter)
      case Right(d) => d.format(formatter)
    }

    Token(strValue, TokenType.TEMPORAL)
  }
}

// ============================================================================
// Advanced: Union Types and Overloads
// ============================================================================

class UniversalTokenizer {
  private val _stringTokenizer = new StringTokenizer()
  private val _numericTokenizer = new NumericTokenizer()
  private val _temporalTokenizer = new TemporalTokenizer()

  def tokenize(value: String): Token = _stringTokenizer.tokenize(Left(value))
  def tokenize(value: Array[Byte]): Token = _stringTokenizer.tokenize(Right(value))
  def tokenize(value: Int): Token = _numericTokenizer.tokenize(value)
  def tokenize(value: Long): Token = _numericTokenizer.tokenize(value)
  def tokenize(value: Double): Token = _numericTokenizer.tokenize(value)
  def tokenize(value: Float): Token = _numericTokenizer.tokenize(value)
  def tokenize(value: BigDecimal): Token = _numericTokenizer.tokenize(value)
  def tokenize(value: LocalDateTime): Token = _temporalTokenizer.tokenize(Left(value))
  def tokenize(value: LocalDate): Token = _temporalTokenizer.tokenize(Right(value))
  
  def tokenizeNull: Token = Token("NULL", TokenType.NULL)
  
  def tokenize(value: Tokenizable): Token = Token(value.toToken, TokenType.STRUCTURED)

  def tokenize(value: Any): Token = {
    if (value == null) {
      return tokenizeNull
    }

    value match {
      case t: Tokenizable => tokenize(t)
      case s: String => tokenize(s)
      case b: Array[Byte] => tokenize(b)
      case i: Int => tokenize(i)
      case l: Long => tokenize(l)
      case d: Double => tokenize(d)
      case f: Float => tokenize(f)
      case bd: BigDecimal => tokenize(bd)
      case dt: LocalDateTime => tokenize(dt)
      case d: LocalDate => tokenize(d)
      case _ => Token(value.toString, TokenType.STRING, Map("fallback" -> true))
    }
  }
}

// ============================================================================
// Complex Nested Generics
// ============================================================================

class TokenRegistry[T] {
  private val _registry: mutable.Map[String, TokenContainer[T]] = mutable.Map.empty
  private val _handlers: mutable.ListBuffer[T => Option[Token]] = mutable.ListBuffer.empty

  def register(key: String, container: TokenContainer[T]): Unit = {
    _registry(key) = container
  }

  def addHandler(handler: T => Option[Token]): Unit = {
    _handlers += handler
  }

  def process(key: String): List[Option[Token]] = {
    _registry.get(key) match {
      case None => Nil
      case Some(container) =>
        container.getAll.toList.map { item =>
          _handlers.iterator
            .map(handler => handler(item))
            .find(_.isDefined)
            .flatten
        }
    }
  }
}

// ============================================================================
// Higher-Kinded Type Simulation
// ============================================================================

class TokenFunctor[T](private val _value: T) {
  
  def map[B](func: T => B): TokenFunctor[B] = {
    new TokenFunctor(func(_value))
  }

  def flatMap[B](func: T => TokenFunctor[B]): TokenFunctor[B] = {
    func(_value)
  }

  def getOrElse(default: => T): T = {
    if (_value != null) _value else default
  }
  
  def get: T = _value
}

class TokenMonad[T](value: T) extends TokenFunctor[T](value) {
  
  def ap[B](funcWrapped: TokenMonad[T => B]): TokenMonad[B] = {
    new TokenMonad(funcWrapped.get(this.get))
  }
}

object TokenMonad {
  def pure[T](value: T): TokenMonad[T] = new TokenMonad(value)
}

// ============================================================================
// JSON Structure Tokenization
// ============================================================================

class JsonTokenizer(pretty: Boolean = false) {
  
  def tokenize(value: Json): Token = {
    val jsonStr = if (pretty) value.spaces2 else value.noSpaces
    Token(jsonStr, TokenType.STRUCTURED, Map("json" -> true))
  }

  def tokenizePath(value: Json, path: String): Option[Token] = {
    val parts = path.split("\\.")
    var current: Option[Json] = Some(value)

    for (part <- parts) {
      current = current.flatMap { json =>
        if (json.isObject) {
          json.asObject.flatMap(_.apply(part))
        } else if (json.isArray && part.forall(_.isDigit)) {
          val idx = part.toInt
          json.asArray.flatMap { arr =>
            if (idx >= 0 && idx < arr.size) Some(arr(idx)) else None
          }
        } else {
          None
        }
      }
    }

    current.map(tokenize)
  }
}

// ============================================================================
// Whitespace Tokenizer - Basic Text Tokenization
// ============================================================================

class WhitespaceTokenizer(
    lowercase: Boolean = false,
    minLength: Int = 0,
    maxLength: Option[Int] = None,
    stripPunctuation: Boolean = false
) {
  private val _punctuation = Set('.', ',', '!', '?', ';', ':', '\'', '"', '(', ')', '[', ']', '{', '}')

  private def _processToken(word: String): Option[String] = {
    var processed = word
    if (stripPunctuation) {
      processed = processed.dropWhile(_punctuation.contains).reverse.dropWhile(_punctuation.contains).reverse
    }

    if (lowercase) {
      processed = processed.toLowerCase
    }

    if (processed.length < minLength) {
      return None
    }

    maxLength match {
      case Some(max) if processed.length > max => processed = processed.take(max)
      case _ =>
    }

    if (processed.nonEmpty) Some(processed) else None
  }

  def tokenize(text: String): List[Token] = {
    val words = text.split("\\s+")
    
    words.zipWithIndex.flatMap { case (word, i) =>
      _processToken(word).map { processed =>
        Token(
          value = processed,
          tokenType = TokenType.STRING,
          metadata = Map("position" -> i, "original" -> word)
        )
      }
    }.toList
  }

  def tokenizeToStrings(text: String): List[String] = {
    tokenize(text).map(_.value)
  }

  def tokenizeWithPositions(text: String): List[(String, Int, Int)] = {
    val words = text.split("\\s+")
    var currentPos = 0
    val result = mutable.ListBuffer[(String, Int, Int)]()

    for (word <- words) {
      val start = text.indexOf(word, currentPos)
      if (start >= 0) {
        val end = start + word.length
        
        _processToken(word).foreach { processed =>
          result += ((processed, start, end))
        }
        
        currentPos = end
      }
    }

    result.toList
  }

  def countTokens(text: String): Int = {
    tokenize(text).length
  }
}

// ============================================================================
// Builder Pattern with Fluent Interface
// ============================================================================

class TokenizerBuilder[T] private (
    private val _normalizers: List[String => String] = Nil,
    private val _validators: List[T => Boolean] = Nil,
    private val _metadata: Map[String, Any] = Map.empty
) {
  def withNormalizer(normalizer: String => String): TokenizerBuilder[T] = {
    new TokenizerBuilder[T](_normalizers :+ normalizer, _validators, _metadata)
  }

  def withValidator(validator: T => Boolean): TokenizerBuilder[T] = {
    new TokenizerBuilder[T](_normalizers, _validators :+ validator, _metadata)
  }

  def withMetadata(kwargs: (String, Any)*): TokenizerBuilder[T] = {
    new TokenizerBuilder[T](_normalizers, _validators, _metadata ++ kwargs.toMap)
  }

  def build(): T => Token = {
    val normalizers = _normalizers
    val validators = _validators
    val metadata = _metadata

    (value: T) => {
      // Validate
      for (validator <- validators) {
        if (!validator(value)) {
          throw new IllegalArgumentException(s"Validation failed for $value")
        }
      }

      // Convert to string
      var strValue = value.toString

      // Normalize
      for (normalizer <- normalizers) {
        strValue = normalizer(strValue)
      }

      Token(strValue, TokenType.STRING, metadata)
    }
  }
}

object TokenizerBuilder {
  def apply[T](): TokenizerBuilder[T] = new TokenizerBuilder[T]()
}
