#!/usr/bin/env python3

import sys

import atheris


with atheris.instrument_imports():
    from IPython.core.inputtransformer2 import TransformerManager
    from IPython.core.splitinput import split_user_input


def _consume_cell(fdp: atheris.FuzzedDataProvider) -> str:
    # Keep cells reasonably small to avoid pathological slowdowns.
    cell = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 2048))
    return cell


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    cell = _consume_cell(fdp)

    try:
        # Exercise line splitter on the first line.
        first_line = cell.splitlines()[0] if cell else ""
        _ = split_user_input(first_line)

        tm = TransformerManager()
        _ = tm.transform_cell(cell)
        status, indent = tm.check_complete(cell)
        if status not in {"complete", "incomplete", "invalid"}:
            raise AssertionError(f"Unexpected completion status: {status!r}")
        if status == "incomplete" and indent is not None and not isinstance(indent, int):
            raise AssertionError("indent_spaces should be int|None")

    except (SyntaxError, ValueError):
        return
    except RuntimeError as e:
        # TransformerManager uses a loop limit to avoid infinite transformations.
        if "Input transformation still changing" in str(e):
            return
        raise


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
