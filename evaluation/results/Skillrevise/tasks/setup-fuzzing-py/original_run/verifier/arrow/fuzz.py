#!/usr/bin/env python3

import sys

import atheris

with atheris.instrument_imports():
    import arrow
    from arrow import parser


_DT_PARSER = parser.DateTimeParser()
_FORMATS = [
    "YYYY-MM-DD",
    "YYYY/MM/DD",
    "YYYY.MM.DD",
    "YYYY-MM-DD HH:mm:ss",
    "YYYY-MM-DDTHH:mm:ssZ",
    "YYYY-MM-DDTHH:mm:ss.SZ",
    "DD/MM/YYYY",
    "D/M/YYThh:mm:ss.SZ",
]


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    s = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 512))
    normalize_ws = fdp.ConsumeBool()

    try:
        if fdp.ConsumeBool():
            dt = _DT_PARSER.parse_iso(s, normalize_whitespace=normalize_ws)
        else:
            fmt = fdp.PickValueInList(_FORMATS)
            dt = _DT_PARSER.parse(s, fmt, normalize_whitespace=normalize_ws)

        # Cheap round-trip: ensure we can parse an isoformat() output.
        _DT_PARSER.parse_iso(dt.isoformat())

        # Also exercise the public factory surface.
        arrow.get(dt)
    except (
        parser.ParserError,
        parser.ParserMatchError,
        ValueError,
        TypeError,
        OverflowError,
    ):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
