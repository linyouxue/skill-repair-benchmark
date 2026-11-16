#!/usr/bin/env python3

import sys

import atheris


with atheris.instrument_imports():
    import ujson


def _consume_text(fdp: atheris.FuzzedDataProvider, max_chars: int) -> str:
    return fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, max_chars))


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    s = _consume_text(fdp, 2048)

    try:
        obj = ujson.loads(s)
    except (ValueError, TypeError, OverflowError):
        return

    try:
        opts = {
            "ensure_ascii": bool(fdp.ConsumeIntInRange(0, 1)),
            "encode_html_chars": bool(fdp.ConsumeIntInRange(0, 1)),
            "escape_forward_slashes": bool(fdp.ConsumeIntInRange(0, 1)),
        }
        if fdp.ConsumeIntInRange(0, 4) == 0:
            opts["indent"] = fdp.ConsumeIntInRange(0, 8)

        dumped = ujson.dumps(obj, **opts)
        _ = ujson.loads(dumped)

    except (ValueError, TypeError, OverflowError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
