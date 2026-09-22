#!/usr/bin/env python3
import os
import sys

import atheris

REPO_ROOT = os.path.dirname(__file__)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

with atheris.instrument_imports():
    import ujson


def _gen_json_value(fdp: atheris.FuzzedDataProvider, depth: int):
    # Limit depth to avoid exponential structures.
    if depth <= 0:
        choice = fdp.ConsumeIntInRange(0, 4)
    else:
        choice = fdp.ConsumeIntInRange(0, 6)

    if choice == 0:
        return None
    if choice == 1:
        return fdp.ConsumeBool()
    if choice == 2:
        return fdp.ConsumeInt(8)
    if choice == 3:
        return fdp.ConsumeRegularFloat()
    if choice == 4:
        n = fdp.ConsumeIntInRange(0, 64)
        return fdp.ConsumeUnicodeNoSurrogates(n)
    if choice == 5:
        n = fdp.ConsumeIntInRange(0, 16)
        return [_gen_json_value(fdp, depth - 1) for _ in range(n)]

    # dict
    n = fdp.ConsumeIntInRange(0, 16)
    out = {}
    for _ in range(n):
        k = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 32))
        out[k] = _gen_json_value(fdp, depth - 1)
    return out


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    if len(data) > 1_000_000:
        return

    mode = fdp.ConsumeIntInRange(0, 1)

    if mode == 0:
        # Fuzz loads on arbitrary text.
        s = fdp.ConsumeBytes(fdp.ConsumeIntInRange(0, 8192)).decode("utf-8", "replace")
        try:
            ujson.loads(s)
        except (ValueError, TypeError, OverflowError):
            return
    else:
        # Fuzz dumps on generated JSON-serializable objects.
        obj = _gen_json_value(fdp, depth=3)
        indent = fdp.ConsumeIntInRange(0, 4)
        ensure_ascii = fdp.ConsumeBool()
        encode_html_chars = fdp.ConsumeBool()
        escape_forward_slashes = fdp.ConsumeBool()

        try:
            dumped = ujson.dumps(
                obj,
                indent=indent,
                ensure_ascii=ensure_ascii,
                encode_html_chars=encode_html_chars,
                escape_forward_slashes=escape_forward_slashes,
            )
        except (ValueError, TypeError, OverflowError):
            return

        # Round-trip should not crash.
        try:
            ujson.loads(dumped)
        except ValueError:
            return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
