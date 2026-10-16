#!/usr/bin/env python3

import sys

import atheris


with atheris.instrument_imports():
    from minisgl.env import _PARSE_MEM_BYTES


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    s = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 64))
    try:
        out = _PARSE_MEM_BYTES(s)
        if not isinstance(out, int):
            raise AssertionError("_PARSE_MEM_BYTES did not return int")
    except (ValueError, KeyError, IndexError, OverflowError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
