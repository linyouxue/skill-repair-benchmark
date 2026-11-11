#!/usr/bin/env python3
"""Atheris LibFuzzer harness for `minisgl.env._PARSE_MEM_BYTES`.

The full minisgl distribution has heavy GPU/ML dependencies (torch,
flashinfer, sgl_kernel, ...). We deliberately target a pure-Python
parser inside the package and extend sys.path to the source tree instead
of running `pip install .`.
"""
import os
import sys
import atheris

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))

with atheris.instrument_imports():
    from minisgl.env import _PARSE_MEM_BYTES

INVALID_INPUT_EXCEPTIONS = (
    ValueError,
    KeyError,
    IndexError,
    OverflowError,
)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    s = fdp.ConsumeUnicodeNoSurrogates(fdp.remaining_bytes())
    try:
        _PARSE_MEM_BYTES(s)
    except INVALID_INPUT_EXCEPTIONS:
        return


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
