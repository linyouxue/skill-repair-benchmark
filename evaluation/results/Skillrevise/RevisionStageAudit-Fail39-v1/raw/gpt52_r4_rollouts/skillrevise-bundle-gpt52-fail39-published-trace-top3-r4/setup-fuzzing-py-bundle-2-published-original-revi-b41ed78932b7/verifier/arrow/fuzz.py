import sys

import atheris

with atheris.instrument_imports():
    import arrow
    from arrow.parser import DateTimeParser, ParserError


_COMMON_FORMATS: list[str] = [
    "YYYY-MM-DD",
    "YYYY-MM-DD HH:mm:ss",
    "YYYY-MM-DDTHH:mm:ssZ",
    "YYYY-MM-DDTHH:mm:ss.SSSZ",
    "MM/DD/YYYY",
    "DD/MM/YY",
    "X",
    "x",
]


def _consume_text(fdp: atheris.FuzzedDataProvider, max_len: int) -> str:
    try:
        return fdp.ConsumeUnicodeNoSurrogates(max_len)
    except AttributeError:
        return fdp.ConsumeBytes(max_len).decode("utf-8", errors="ignore")


_PARSER = DateTimeParser()


def TestOneInput(data: bytes) -> None:
    data = data[:8192]
    fdp = atheris.FuzzedDataProvider(data)

    which = fdp.ConsumeIntInRange(0, 2)
    s = _consume_text(fdp, 256)
    if not s:
        return

    fmt_choice = _COMMON_FORMATS[fdp.ConsumeIntInRange(0, len(_COMMON_FORMATS) - 1)]
    maybe_fmt = _consume_text(fdp, 64)

    try:
        if which == 0:
            if fdp.ConsumeBool():
                arrow.get(s)
            elif fdp.ConsumeBool():
                arrow.get(s, fmt_choice)
            else:
                arrow.get(s, [fmt_choice, maybe_fmt])
        elif which == 1:
            if fdp.ConsumeBool():
                _PARSER.parse(s, fmt_choice)
            else:
                _PARSER.parse(s, [fmt_choice, maybe_fmt])
        else:
            arrow.utcnow().dehumanize(s, locale="en_us")
    except (ParserError, ValueError, OverflowError, TypeError):
        return


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
