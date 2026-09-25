#!/usr/bin/env python3

import sys
import tokenize

import atheris

with atheris.instrument_imports():
    from IPython.core.inputtransformer2 import TransformerManager
    from IPython.core.splitinput import split_user_input


_TM = TransformerManager()


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    cell = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 2048))

    # Smaller, line-oriented target.
    line = cell.split("\n", 1)[0]

    try:
        split_user_input(line)
        _TM.check_complete(cell)
        _TM.transform_cell(cell)
    except (SyntaxError, tokenize.TokenError, ValueError, TypeError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
