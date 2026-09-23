#!/usr/bin/env python3
import sys

import atheris

with atheris.instrument_imports():
    import ujson


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    # Bound input size; JSON parsers can be quadratic on some patterns.
    data = data[:20000]

    try:
        # Exercise both bytes and str entry paths.
        if data and data[0] % 2 == 0:
            ujson.loads(data)
        else:
            s = data.decode("utf-8", errors="ignore")
            ujson.loads(s)
    except (ValueError, OverflowError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
