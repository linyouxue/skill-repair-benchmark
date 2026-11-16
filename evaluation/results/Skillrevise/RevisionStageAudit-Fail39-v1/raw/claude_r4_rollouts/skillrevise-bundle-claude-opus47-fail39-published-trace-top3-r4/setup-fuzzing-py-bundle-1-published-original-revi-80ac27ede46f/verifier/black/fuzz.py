#!/usr/bin/env python3
"""Atheris fuzz driver for black.format_str()."""
import sys
import atheris

with atheris.instrument_imports():
    import black
    from black.parsing import InvalidInput as ParsingInvalidInput

EXPECTED = (
    black.InvalidInput,
    ParsingInvalidInput,
    SyntaxError,
    IndentationError,
    ValueError,
    TypeError,
    AssertionError,
    UnicodeDecodeError,
    UnicodeEncodeError,
    OverflowError,
    RecursionError,
    KeyError,
)

_MODE = black.Mode()


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    src = fdp.ConsumeUnicodeNoSurrogates(len(data))
    try:
        black.format_str(src, mode=_MODE)
    except EXPECTED:
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
