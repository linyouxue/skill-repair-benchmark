#!/usr/bin/env python3

import sys
import tokenize

import atheris


with atheris.instrument_imports():
    import black


def _consume_src(fdp: atheris.FuzzedDataProvider) -> str:
    src = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 4096))
    # Black generally expects text input; ensure there's at least one newline.
    if "\n" not in src:
        src += "\n"
    return src


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    src = _consume_src(fdp)

    mode = black.Mode()

    try:
        dst = black.format_str(src, mode=mode)
        # Basic stability check when formatting succeeds.
        dst2 = black.format_str(dst, mode=mode)
        if dst2 != dst:
            raise AssertionError("black.format_str is not idempotent")

    except (
        black.parsing.InvalidInput,
        SyntaxError,
        IndentationError,
        tokenize.TokenError,
        ValueError,
    ):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
