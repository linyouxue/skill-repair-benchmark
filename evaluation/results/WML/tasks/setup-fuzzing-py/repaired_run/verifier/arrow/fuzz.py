#!/usr/bin/env python3
import os
import sys

import atheris

# Running from /app/arrow already makes local imports work.
with atheris.instrument_imports():
    import arrow
    from arrow import parser as arrow_parser


_FORMAT_SEEDS = [
    "YYYY-MM-DD",
    "YYYY-MM-DD HH:mm:ss",
    "YYYY-MM-DDTHH:mm:ss",
    "YYYY-MM-DDTHH:mm:ss.S",
    "YYYY-MM-DD HH:mm:ss ZZZ",
    "YYYY-MM-DD HH:mm:ss ZZ",
]


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    # Keep Arrow parsing reasonably bounded.
    data = data[:4096]

    # Prefer UTF-8 strings since Arrow's parsing entry points take str.
    s = data.decode("utf-8", errors="ignore")
    if not s:
        return

    fdp = atheris.FuzzedDataProvider(data)

    try:
        which = fdp.ConsumeIntInRange(0, 2)
        if which == 0:
            # ISO-ish parsing path
            arrow.get(s, normalize_whitespace=True)
        elif which == 1:
            fmt = _FORMAT_SEEDS[fdp.ConsumeIntInRange(0, len(_FORMAT_SEEDS) - 1)]
            arrow.get(s, fmt, normalize_whitespace=True)
        else:
            # Multi-format parsing path
            fmts = [
                _FORMAT_SEEDS[fdp.ConsumeIntInRange(0, len(_FORMAT_SEEDS) - 1)],
                _FORMAT_SEEDS[fdp.ConsumeIntInRange(0, len(_FORMAT_SEEDS) - 1)],
            ]
            arrow.get(s, fmts, normalize_whitespace=True)
    except (
        arrow_parser.ParserError,
        ValueError,
        OverflowError,
        TypeError,
    ):
        # Expected for malformed or unsupported inputs.
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
