#!/usr/bin/env python3

import sys

import atheris

with atheris.instrument_imports():
    import ujson


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    s = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 1024))

    try:
        obj = ujson.loads(s)
    except (ValueError, TypeError, OverflowError):
        return

    ensure_ascii = bool(fdp.ConsumeIntInRange(0, 1))
    encode_html_chars = bool(fdp.ConsumeIntInRange(0, 1))
    escape_forward_slashes = bool(fdp.ConsumeIntInRange(0, 1))

    try:
        dumped = ujson.dumps(
            obj,
            ensure_ascii=ensure_ascii,
            encode_html_chars=encode_html_chars,
            escape_forward_slashes=escape_forward_slashes,
        )
        ujson.loads(dumped)
    except (ValueError, TypeError, OverflowError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
