#!/usr/bin/env python3
"""Atheris fuzz driver for arrow.get() string parsing path."""
import sys
import atheris

with atheris.instrument_imports():
    import arrow
    from arrow.parser import ParserError, ParserMatchError

EXPECTED = (
    ParserError,
    ParserMatchError,
    ValueError,
    TypeError,
    OverflowError,
    KeyError,
)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    s = fdp.ConsumeUnicodeNoSurrogates(len(data))
    try:
        arrow.get(s)
    except EXPECTED:
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
