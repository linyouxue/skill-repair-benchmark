#!/usr/bin/env python3

import sys

import atheris


with atheris.instrument_imports():
    import arrow
    from arrow import parser as arrow_parser


COMMON_FORMATS = [
    "YYYY-MM-DD",
    "YYYY-MM-DD HH:mm:ss",
    "YYYY-MM-DDTHH:mm:ss",
    "YYYY-MM-DDTHH:mm:ss.S",
    "YYYY-MM-DDTHH:mm:ss.SZZ",
    "DD/MM/YYYY",
    "DD/MM/YY",
    "D/M/YYYYThh:mm:ss.SZ",
    "YYYYMMDDTHHmmss.S",
    "X",
]

COMMON_TZS = [
    "UTC",
    "local",
    "US/Pacific",
    "Europe/Berlin",
    "+00:00",
    "+02:00",
    "-05:00",
    "Etc/GMT+1",
]


def _consume_reasonable_unicode(fdp: atheris.FuzzedDataProvider, max_chars: int) -> str:
    # Avoid surrogate characters because many libraries treat them inconsistently.
    return fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, max_chars))


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    mode = fdp.ConsumeIntInRange(0, 3)
    s = _consume_reasonable_unicode(fdp, 256)

    try:
        if mode == 0:
            # Public API: best-effort ISO parser.
            arw = arrow.get(s)
            _ = arw.format(fdp.PickValueInList(COMMON_FORMATS))
        elif mode == 1:
            # Explicit formats: exercise DateTimeParser.parse().
            fmt = fdp.PickValueInList(COMMON_FORMATS)
            arw = arrow.get(s, fmt)
            _ = arw.format(fmt)
        elif mode == 2:
            # Multi-format list: exercise _parse_multiformat().
            fmts = [fdp.PickValueInList(COMMON_FORMATS) for _ in range(fdp.ConsumeIntInRange(1, 4))]
            arw = arrow.get(s, fmts)
            _ = arw.format(fdp.PickValueInList(COMMON_FORMATS))
        else:
            # Timezone expression parsing.
            tz_s = fdp.PickValueInList(COMMON_TZS) + _consume_reasonable_unicode(fdp, 32)
            _ = arrow_parser.TzinfoParser.parse(tz_s)

    except (
        arrow_parser.ParserError,
        arrow_parser.ParserMatchError,
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
