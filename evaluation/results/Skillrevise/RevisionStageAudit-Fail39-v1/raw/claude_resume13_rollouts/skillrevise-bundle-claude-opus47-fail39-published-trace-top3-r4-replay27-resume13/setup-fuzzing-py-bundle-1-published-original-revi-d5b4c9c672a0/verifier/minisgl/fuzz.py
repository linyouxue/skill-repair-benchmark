import sys
import atheris

with atheris.instrument_imports():
    from minisgl.env import _PARSE_MEM_BYTES


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    s = fdp.ConsumeUnicodeNoSurrogates(sys.maxsize)
    try:
        _PARSE_MEM_BYTES(s)
    except (ValueError, KeyError, IndexError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
