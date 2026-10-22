"""Atheris fuzz driver for arrow.

Primary target: arrow.parser.DateTimeParser.parse_iso.
Secondary target: arrow.parser.DateTimeParser.parse with a canned format.
Reaches: arrow/parser.py (ISO + format-token parsers).
"""

import sys
import atheris

with atheris.instrument_imports():
    import arrow
    from arrow.parser import DateTimeParser, ParserError

_PARSER = DateTimeParser()

# A couple of canned formats so the second branch exercises the token-driven
# code path in _generate_pattern_re / _parse_token.
_CANNED_FORMATS = [
    "YYYY-MM-DD HH:mm:ss",
    "YYYY-MM-DDTHH:mm:ssZZ",
    "ddd, DD MMM YYYY HH:mm:ss ZZZ",
    "X",
]

# Exceptions already documented as raised by arrow for malformed input.
_EXPECTED = (ParserError, ValueError, TypeError, OverflowError)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    # Choose which parser entrypoint to exercise.
    choice = fdp.ConsumeIntInRange(0, 2)
    s = fdp.ConsumeUnicodeNoSurrogates(1024)

    try:
        if choice == 0:
            _PARSER.parse_iso(s)
        elif choice == 1:
            fmt = _CANNED_FORMATS[fdp.ConsumeIntInRange(0, len(_CANNED_FORMATS) - 1)]
            _PARSER.parse(s, fmt)
        else:
            # Exercise the top-level factory dispatcher.
            arrow.get(s)
    except _EXPECTED:
        pass


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
