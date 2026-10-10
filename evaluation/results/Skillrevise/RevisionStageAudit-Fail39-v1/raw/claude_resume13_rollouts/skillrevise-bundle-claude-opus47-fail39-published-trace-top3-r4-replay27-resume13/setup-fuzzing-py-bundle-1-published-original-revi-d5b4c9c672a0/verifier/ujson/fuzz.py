import sys
import atheris

with atheris.instrument_imports():
    import ujson


def TestOneInput(data: bytes) -> None:
    try:
        ujson.loads(data)
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError, MemoryError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
