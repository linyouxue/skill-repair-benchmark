#!/usr/bin/env python3

import sys

import atheris

with atheris.instrument_imports():
    import black
    from black.parsing import InvalidInput


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    src = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 8192))

    mode = black.Mode(
        line_length=fdp.ConsumeIntInRange(60, 120),
        string_normalization=fdp.ConsumeBool(),
        is_pyi=fdp.ConsumeBool(),
    )

    try:
        out1 = black.format_str(src, mode=mode)
    except (
        InvalidInput,
        black.NothingChanged,
        SyntaxError,
        IndentationError,
        ValueError,
        KeyError,
    ):
        return

    # Stability oracle: formatting twice should not change output.
    out2 = black.format_str(out1, mode=mode)
    if out2 != out1:
        raise AssertionError("Black formatting is not stable")


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
