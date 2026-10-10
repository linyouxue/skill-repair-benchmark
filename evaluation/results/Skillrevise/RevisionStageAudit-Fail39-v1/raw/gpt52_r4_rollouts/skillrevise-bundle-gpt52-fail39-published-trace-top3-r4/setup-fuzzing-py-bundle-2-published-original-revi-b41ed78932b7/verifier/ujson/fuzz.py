import sys

import atheris

with atheris.instrument_imports():
    import ujson


def _consume_text(fdp: atheris.FuzzedDataProvider, max_len: int) -> str:
    try:
        return fdp.ConsumeUnicodeNoSurrogates(max_len)
    except AttributeError:
        return fdp.ConsumeBytes(max_len).decode("utf-8", errors="ignore")


def _build_obj(fdp: atheris.FuzzedDataProvider, depth: int):
    if depth <= 0:
        choice = fdp.ConsumeIntInRange(0, 5)
        if choice == 0:
            return None
        if choice == 1:
            return fdp.ConsumeBool()
        if choice == 2:
            return fdp.ConsumeIntInRange(-2**31, 2**31 - 1)
        if choice == 3:
            return fdp.ConsumeFloat()
        if choice == 4:
            return _consume_text(fdp, 64)
        return fdp.ConsumeBytes(16)

    kind = fdp.ConsumeIntInRange(0, 2)
    if kind == 0:
        return _build_obj(fdp, 0)
    if kind == 1:
        n = fdp.ConsumeIntInRange(0, 8)
        return [_build_obj(fdp, depth - 1) for _ in range(n)]

    n = fdp.ConsumeIntInRange(0, 8)
    d = {}
    for _ in range(n):
        k = _consume_text(fdp, 32)
        d[k] = _build_obj(fdp, depth - 1)
    return d


def TestOneInput(data: bytes) -> None:
    data = data[:16384]
    fdp = atheris.FuzzedDataProvider(data)

    try:
        if fdp.ConsumeBool():
            payload = fdp.ConsumeBytes(4096)
            try:
                ujson.loads(payload)
            except TypeError:
                ujson.loads(payload.decode("utf-8", errors="ignore"))
        else:
            obj = _build_obj(fdp, depth=3)
            s = ujson.dumps(obj)
            ujson.loads(s)
    except (ValueError, OverflowError, TypeError, UnicodeDecodeError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
