import sys
import atheris

with atheris.instrument_imports():
    import black


_MODE = black.Mode()


def TestOneInput(data: bytes) -> None:
    try:
        src = data.decode("utf-8", errors="replace")
    except Exception:
        return
    try:
        black.format_str(src, mode=_MODE)
    except (
        black.InvalidInput,
        black.NothingChanged,
        SyntaxError,
        IndentationError,
        ValueError,
        AssertionError,
        RecursionError,
        UnicodeDecodeError,
        UnicodeEncodeError,
        # blib2to3 occasionally surfaces malformed-source cases as these:
        KeyError,
        AttributeError,
        LookupError,
    ):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
