"""Atheris fuzz driver for ujson (ultrajson).

Primary target: ujson.loads — the C JSON decoder.
Secondary target: ujson.dumps — the C JSON encoder round-tripped against
structured Python objects produced from the fuzz input.
"""

import sys
import atheris

with atheris.instrument_imports():
    import ujson


_LOADS_EXPECTED = (ValueError, TypeError, UnicodeDecodeError)
_DUMPS_EXPECTED = (TypeError, ValueError, OverflowError, RecursionError)


def _build_object(fdp: atheris.FuzzedDataProvider, depth: int = 0):
    """Build a small, JSON-serialisable Python object from the fuzz input."""
    if depth >= 4:
        kind = fdp.ConsumeIntInRange(0, 3)
    else:
        kind = fdp.ConsumeIntInRange(0, 6)
    if kind == 0:
        return None
    if kind == 1:
        return fdp.ConsumeBool()
    if kind == 2:
        return fdp.ConsumeIntInRange(-(1 << 60), 1 << 60)
    if kind == 3:
        return fdp.ConsumeUnicodeNoSurrogates(64)
    if kind == 4:
        return fdp.ConsumeFloat()
    if kind == 5:
        n = fdp.ConsumeIntInRange(0, 4)
        return [_build_object(fdp, depth + 1) for _ in range(n)]
    n = fdp.ConsumeIntInRange(0, 4)
    return {
        fdp.ConsumeUnicodeNoSurrogates(16): _build_object(fdp, depth + 1)
        for _ in range(n)
    }


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    mode = fdp.ConsumeIntInRange(0, 2)

    if mode == 0:
        # Decode a raw bytes payload.
        buf = fdp.ConsumeBytes(atheris.ALL_REMAINING)
        try:
            ujson.loads(buf)
        except _LOADS_EXPECTED:
            pass
    elif mode == 1:
        # Decode a text payload.
        s = fdp.ConsumeUnicodeNoSurrogates(atheris.ALL_REMAINING)
        try:
            ujson.loads(s)
        except _LOADS_EXPECTED:
            pass
    else:
        # Encode a structured Python object, then round-trip it.
        obj = _build_object(fdp)
        try:
            encoded = ujson.dumps(obj)
        except _DUMPS_EXPECTED:
            return
        try:
            ujson.loads(encoded)
        except _LOADS_EXPECTED:
            pass


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
