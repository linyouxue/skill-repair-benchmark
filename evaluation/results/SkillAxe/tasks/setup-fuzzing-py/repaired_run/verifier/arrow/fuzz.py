#!/usr/bin/env python3
import os
import sys

import atheris

REPO_ROOT = os.path.dirname(__file__)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

with atheris.instrument_imports():
    import arrow
    from arrow.formatter import DateTimeFormatter
    from arrow.parser import DateTimeParser, ParserError


_PARSER = DateTimeParser()
_FORMATTER = DateTimeFormatter()


def _limited_unicode(fdp: atheris.FuzzedDataProvider, max_chars: int) -> str:
    n = fdp.ConsumeIntInRange(0, max_chars)
    return fdp.ConsumeUnicodeNoSurrogates(n)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    # Keep runtime bounded.
    if len(data) > 1_000_000:
        return

    choice = fdp.ConsumeIntInRange(0, 3)

    if choice == 0:
        # Structured-ish ISO timestamp (more likely to reach deep parsing).
        year = fdp.ConsumeIntInRange(1, 9999)
        month = fdp.ConsumeIntInRange(1, 12)
        day = fdp.ConsumeIntInRange(1, 28)
        hour = fdp.ConsumeIntInRange(0, 23)
        minute = fdp.ConsumeIntInRange(0, 59)
        second = fdp.ConsumeIntInRange(0, 59)
        s = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"

        try:
            a = arrow.get(s)
        except (ParserError, ValueError, OverflowError, TypeError):
            return

        fmt = _limited_unicode(fdp, 64)
        if fmt:
            try:
                _FORMATTER.format(a._datetime, fmt)
            except (KeyError, ValueError, OverflowError):
                return

        # Round-trip sanity when we have a value.
        try:
            iso = a.isoformat()
            arrow.get(iso)
        except (ParserError, ValueError, OverflowError, TypeError):
            return

    elif choice == 1:
        # Unstructured string parsing.
        s = _limited_unicode(fdp, 256)
        try:
            arrow.get(s)
        except (ParserError, ValueError, OverflowError, TypeError):
            return

    elif choice == 2:
        # Explicit format parsing drives DateTimeParser.
        year = fdp.ConsumeIntInRange(1, 9999)
        month = fdp.ConsumeIntInRange(1, 12)
        day = fdp.ConsumeIntInRange(1, 28)
        s = f"{year:04d}-{month:02d}-{day:02d}"
        try:
            _PARSER.parse(s, "YYYY-MM-DD")
        except (ParserError, ValueError, OverflowError, TypeError):
            return

    else:
        # Timestamp conversions.
        ts = fdp.ConsumeRegularFloat()
        try:
            a = arrow.Arrow.fromtimestamp(ts)
            a.timestamp()
        except (ValueError, OverflowError, TypeError, OSError):
            return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
