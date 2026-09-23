#!/usr/bin/env python3
import os
import sys

import atheris

# Black uses src/ layout.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "src"))

with atheris.instrument_imports():
    import black

try:
    from blib2to3.pgen2.tokenize import TokenError
except Exception:  # pragma: no cover
    TokenError = Exception


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    # Bound input size to keep formatting tractable.
    data = data[:20000]
    src = data.decode("utf-8", errors="ignore")

    # Avoid spending time on trivially huge no-op strings.
    if not src:
        return

    try:
        black.format_str(src, mode=black.Mode())
    except (
        black.InvalidInput,
        black.NothingChanged,
        SyntaxError,
        IndentationError,
        TokenError,
        ValueError,
        KeyError,  # e.g. blib2to3 grammar.opmap failures on invalid tokens
    ):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
