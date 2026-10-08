#!/usr/bin/env python3

import sys

import atheris

with atheris.instrument_imports():
    from minisgl import env as minisgl_env


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    # Keep inputs small; this is a pure parsing helper.
    s = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 64))

    try:
        minisgl_env._PARSE_MEM_BYTES(s)
        minisgl_env._TO_BOOL(s)
    except (ValueError, KeyError, IndexError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
