import sys

import atheris

with atheris.instrument_imports():
    import black
    from black.parsing import InvalidInput
    from black.report import NothingChanged
    from blib2to3.pgen2.tokenize import TokenError


_MODE = black.Mode()


def TestOneInput(data: bytes) -> None:
    data = data[:16384]
    fdp = atheris.FuzzedDataProvider(data)

    try:
        if fdp.ConsumeBool():
            src = fdp.ConsumeBytes(8192)
            contents, _, _ = black.decode_bytes(src, _MODE)
            black.format_file_contents(contents, fast=True, mode=_MODE)
        else:
            try:
                src_txt = fdp.ConsumeUnicodeNoSurrogates(8192)
            except AttributeError:
                src_txt = fdp.ConsumeBytes(8192).decode("utf-8", errors="ignore")
            black.format_str(src_txt, mode=_MODE)
    except (
        InvalidInput,
        NothingChanged,
        SyntaxError,
        IndentationError,
        TokenError,
        KeyError,
        ValueError,
        OverflowError,
    ):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
