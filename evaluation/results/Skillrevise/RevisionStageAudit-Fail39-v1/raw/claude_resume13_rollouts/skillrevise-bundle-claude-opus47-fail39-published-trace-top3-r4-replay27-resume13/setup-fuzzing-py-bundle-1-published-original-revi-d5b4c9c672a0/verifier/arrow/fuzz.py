import sys
import atheris

with atheris.instrument_imports():
    import arrow
    from arrow.parser import ParserError, ParserMatchError


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    mode = fdp.ConsumeIntInRange(0, 2)
    s = fdp.ConsumeUnicodeNoSurrogates(sys.maxsize)
    try:
        if mode == 0:
            arrow.get(s)
        elif mode == 1:
            fmt = fdp.ConsumeUnicodeNoSurrogates(64)
            arrow.get(s, fmt)
        else:
            arrow.get(s, tzinfo=fdp.ConsumeUnicodeNoSurrogates(32))
    except (
        ParserError,
        ParserMatchError,
        ValueError,
        TypeError,
        OverflowError,
        AttributeError,
        KeyError,
    ):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
