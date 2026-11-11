#!/usr/bin/env python3
"""Atheris LibFuzzer harness for ujson.

Fuzzes `ujson.loads` on raw bytes and, on successful decode, round-trips
through `ujson.dumps` to also exercise the encoder path.
"""
import sys
import atheris

with atheris.instrument_imports():
    import ujson

INVALID_INPUT_EXCEPTIONS = (
    ValueError,
    TypeError,
    UnicodeDecodeError,
    OverflowError,
    RecursionError,
)


def TestOneInput(data: bytes) -> None:
    # ujson is a C extension — Python bytecode instrumentation sees
    # nothing inside the parser. Instrumenting the harness itself still
    # lets Atheris track that different value categories (object kinds
    # returned by loads) exercise different branches here, which gives
    # LibFuzzer at least a minimal coverage signal.
    try:
        obj = ujson.loads(data)
    except INVALID_INPUT_EXCEPTIONS:
        return
    # Branch on the decoded shape to produce distinguishable coverage.
    if isinstance(obj, dict):
        pass
    elif isinstance(obj, list):
        pass
    elif isinstance(obj, str):
        pass
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, int):
        pass
    elif isinstance(obj, float):
        pass
    elif obj is None:
        pass
    try:
        ujson.dumps(obj)
    except INVALID_INPUT_EXCEPTIONS:
        return


TestOneInput = atheris.instrument_func(TestOneInput)


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
