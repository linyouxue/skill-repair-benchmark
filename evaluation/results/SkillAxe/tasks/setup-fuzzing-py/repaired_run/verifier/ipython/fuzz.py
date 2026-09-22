#!/usr/bin/env python3
import os
import sys
import tokenize

import atheris

REPO_ROOT = os.path.dirname(__file__)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

with atheris.instrument_imports():
    from IPython.core import inputtransformer2 as ipt2
    from IPython.core import splitinput


_MANAGER = ipt2.TransformerManager()


def _limited_unicode(fdp: atheris.FuzzedDataProvider, max_chars: int) -> str:
    n = fdp.ConsumeIntInRange(0, max_chars)
    return fdp.ConsumeUnicodeNoSurrogates(n)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    if len(data) > 1_000_000:
        return

    cell = _limited_unicode(fdp, 20_000)

    # inputtransformer2 assumes lines typically have line-ending markers;
    # ensure the last line ends with one to avoid unspecified behavior.
    if cell and cell[-1] not in "\n\r\x0b\x0c":
        cell += "\n"

    # Exercise split_user_input on a single logical line.
    line = cell.splitlines()[0] if cell else ""
    splitinput.split_user_input(line)

    # TransformerManager boundaries.
    try:
        _MANAGER.check_complete(cell)
        _MANAGER.transform_cell(cell)
    except (SyntaxError, IndentationError, tokenize.TokenError, ValueError, IndexError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
