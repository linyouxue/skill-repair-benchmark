#!/usr/bin/env python3
"""Atheris fuzz driver for IPython's cell input transformer."""
import sys
import tokenize
import atheris

with atheris.instrument_imports():
    from IPython.core.inputtransformer2 import TransformerManager

EXPECTED = (
    SyntaxError,
    IndentationError,
    ValueError,
    TypeError,
    UnicodeError,
    tokenize.TokenError,
    MemoryError,
    IndexError,
)

_TM = TransformerManager()


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    cell = fdp.ConsumeUnicodeNoSurrogates(len(data))
    try:
        _TM.transform_cell(cell)
    except EXPECTED:
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
