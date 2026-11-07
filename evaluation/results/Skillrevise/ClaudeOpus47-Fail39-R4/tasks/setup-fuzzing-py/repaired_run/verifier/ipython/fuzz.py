#!/usr/bin/env python3
"""Atheris LibFuzzer harness for IPython input transformation."""
import sys
import tokenize
import atheris

with atheris.instrument_imports():
    from IPython.core.inputtransformer2 import TransformerManager

TM = TransformerManager()

INVALID_INPUT_EXCEPTIONS = (
    SyntaxError,          # covers IndentationError too
    tokenize.TokenError,
    ValueError,
    UnicodeDecodeError,
)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    cell = fdp.ConsumeUnicodeNoSurrogates(fdp.remaining_bytes())
    try:
        TM.transform_cell(cell)
    except INVALID_INPUT_EXCEPTIONS:
        return


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
