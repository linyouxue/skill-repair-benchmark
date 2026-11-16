import sys
import tokenize
import atheris

with atheris.instrument_imports():
    from IPython.core.inputtransformer2 import TransformerManager


_TM = TransformerManager()


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    cell = fdp.ConsumeUnicodeNoSurrogates(sys.maxsize)
    try:
        _TM.transform_cell(cell)
    except (
        SyntaxError,
        IndentationError,
        tokenize.TokenError,
        ValueError,
        UnicodeDecodeError,
        UnicodeEncodeError,
        # IPython's transformers surface malformed-cell edges as these:
        IndexError,
        AttributeError,
        KeyError,
    ):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
