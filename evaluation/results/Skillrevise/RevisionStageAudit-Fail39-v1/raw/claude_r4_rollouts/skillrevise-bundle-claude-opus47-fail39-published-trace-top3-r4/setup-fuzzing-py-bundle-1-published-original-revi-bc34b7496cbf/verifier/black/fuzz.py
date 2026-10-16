"""Atheris fuzz driver for black.

Primary target: black.format_str — the main public text-in/text-out entry
point. Reaches lib2to3 tokenizer/parser, AST normalisation, line generation,
and string-literal handling.
"""

import sys
import tokenize

import atheris

with atheris.instrument_imports():
    import black
    from black import InvalidInput, Mode, NothingChanged, format_str
    from black.parsing import ASTSafetyError

_MODE = Mode()

# Exceptions black documents or legitimately raises on malformed input.
_EXPECTED = (
    NothingChanged,
    InvalidInput,
    ASTSafetyError,
    SyntaxError,
    IndentationError,
    tokenize.TokenError,
    ValueError,
    AssertionError,  # black uses assert_stable / assert_equivalent internally
    RecursionError,
)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    src = fdp.ConsumeUnicodeNoSurrogates(4096)
    try:
        format_str(src, mode=_MODE)
    except _EXPECTED:
        pass


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
