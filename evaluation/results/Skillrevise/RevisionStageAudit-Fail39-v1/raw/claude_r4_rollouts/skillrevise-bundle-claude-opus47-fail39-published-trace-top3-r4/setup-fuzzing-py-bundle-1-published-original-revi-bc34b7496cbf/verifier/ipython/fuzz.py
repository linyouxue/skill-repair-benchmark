"""Atheris fuzz driver for IPython.

Primary target: IPython.core.inputtransformer2.TransformerManager.transform_cell —
the raw-cell → valid-Python transformer pipeline (magics, shell escapes, help,
continuations, token-level rewriting).
"""

import sys
import tokenize

import atheris

with atheris.instrument_imports():
    from IPython.core.inputtransformer2 import TransformerManager

_TM = TransformerManager()

_EXPECTED = (
    SyntaxError,
    IndentationError,
    tokenize.TokenError,
    ValueError,
    IndexError,  # observed from degenerate token streams
)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    src = fdp.ConsumeUnicodeNoSurrogates(4096)

    try:
        _TM.transform_cell(src)
    except _EXPECTED:
        pass

    # Also exercise check_complete, which uses a related but distinct code path.
    try:
        _TM.check_complete(src)
    except _EXPECTED:
        pass


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
