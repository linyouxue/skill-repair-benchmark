#!/usr/bin/env python3
import os
import sys

import atheris

# minisgl sources live under python/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "python"))

with atheris.instrument_imports():
    from minisgl import env as minisgl_env


_UNITS = ["", "K", "KB", "M", "MB", "G", "GB", "T", "TB", "B", "X"]


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    data = data[:2048]
    fdp = atheris.FuzzedDataProvider(data)

    # Sometimes use raw decoded input, sometimes a structured-ish mem string.
    if fdp.ConsumeBool():
        s = data.decode("utf-8", errors="ignore")
    else:
        num = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 16)).strip()
        if not num:
            num = str(fdp.ConsumeIntInRange(0, 10_000_000))
        unit = _UNITS[fdp.ConsumeIntInRange(0, len(_UNITS) - 1)]
        s = f"{num}{unit}"

    s = s.strip()
    if not s:
        return

    try:
        minisgl_env._PARSE_MEM_BYTES(s)
    except (ValueError, KeyError, OverflowError):
        # Expected for malformed inputs.
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
