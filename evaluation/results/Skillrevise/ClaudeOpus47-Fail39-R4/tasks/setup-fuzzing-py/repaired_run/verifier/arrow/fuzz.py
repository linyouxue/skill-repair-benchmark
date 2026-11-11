#!/usr/bin/env python3
"""Atheris LibFuzzer harness for the `arrow` library.

Target: `arrow.get(<string>)` — the main user-input datetime parser.
Documented invalid-input exceptions are caught and treated as early returns.
Anything else propagates and will be reported as a real crash by LibFuzzer.
"""
import sys
import atheris

with atheris.instrument_imports():
    import arrow
    from arrow.parser import ParserError

try:
    from zoneinfo import ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfoNotFoundError  # type: ignore

INVALID_INPUT_EXCEPTIONS = (
    ParserError,
    ValueError,
    TypeError,
    OverflowError,
    ZoneInfoNotFoundError,
)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    s = fdp.ConsumeUnicodeNoSurrogates(fdp.remaining_bytes())
    try:
        arrow.get(s)
    except INVALID_INPUT_EXCEPTIONS:
        return


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
