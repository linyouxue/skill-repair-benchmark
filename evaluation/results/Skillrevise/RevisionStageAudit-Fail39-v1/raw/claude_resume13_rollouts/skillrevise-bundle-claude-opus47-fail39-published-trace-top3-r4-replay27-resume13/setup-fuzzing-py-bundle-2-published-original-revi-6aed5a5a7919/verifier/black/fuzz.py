#!/usr/bin/env python3
"""Atheris LibFuzzer harness for `black.format_str`."""
import sys
import atheris

with atheris.instrument_imports():
    import black
    from black.parsing import ASTSafetyError

MODE = black.Mode()

INVALID_INPUT_EXCEPTIONS = (
    black.InvalidInput,
    ASTSafetyError,
    IndentationError,
    SyntaxError,
    ValueError,
    UnicodeDecodeError,
    UnicodeEncodeError,
    RecursionError,
)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    src = fdp.ConsumeUnicodeNoSurrogates(fdp.remaining_bytes())
    try:
        black.format_str(src, mode=MODE)
    except INVALID_INPUT_EXCEPTIONS:
        return


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
