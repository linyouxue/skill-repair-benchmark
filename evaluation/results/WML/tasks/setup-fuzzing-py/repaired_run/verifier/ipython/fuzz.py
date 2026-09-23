#!/usr/bin/env python3
import sys

import atheris

with atheris.instrument_imports():
    from IPython.core.inputtransformer2 import TransformerManager

try:
    from tokenize import TokenError
except Exception:  # pragma: no cover
    TokenError = Exception

_TM = TransformerManager()


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    data = data[:20000]
    s = data.decode("utf-8", errors="ignore")
    if not s:
        return

    try:
        _TM.transform_cell(s)
    except (SyntaxError, IndentationError, TokenError, ValueError):
        # Expected for malformed python/IPython inputs.
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
