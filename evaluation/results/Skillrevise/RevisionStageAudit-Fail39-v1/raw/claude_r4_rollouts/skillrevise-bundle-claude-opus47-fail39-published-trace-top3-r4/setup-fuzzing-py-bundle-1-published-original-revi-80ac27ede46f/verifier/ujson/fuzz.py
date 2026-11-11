#!/usr/bin/env python3
"""Atheris fuzz driver for ujson.loads()."""
import sys
import atheris

with atheris.instrument_imports():
    import ujson

EXPECTED = (
    ValueError,
    TypeError,
    UnicodeDecodeError,
    OverflowError,
    RecursionError,
    MemoryError,
)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    try:
        ujson.loads(data)
    except EXPECTED:
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
