import sys
import tokenize

import atheris

with atheris.instrument_imports():
    from IPython.core.inputtransformer2 import TransformerManager
    from IPython.core.splitinput import split_user_input


_TM = TransformerManager()


def TestOneInput(data: bytes) -> None:
    data = data[:16384]
    fdp = atheris.FuzzedDataProvider(data)
    which = fdp.ConsumeIntInRange(0, 2)

    try:
        cell = fdp.ConsumeUnicodeNoSurrogates(4096)
    except AttributeError:
        cell = fdp.ConsumeBytes(4096).decode("utf-8", errors="ignore")

    try:
        if which == 0:
            _TM.transform_cell(cell)
        elif which == 1:
            _TM.check_complete(cell)
        else:
            split_user_input(cell)
    except (SyntaxError, IndentationError, tokenize.TokenError, ValueError, AssertionError, TypeError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
