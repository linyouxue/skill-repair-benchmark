"""Small, dependency-free helpers for network fetching.

This Skill bundle is often used in sandboxed environments where:
- `requests` may be unavailable
- `HTTP(S)_PROXY` may cause connection resets
- Some hosts (notably imf.org) return 403 unless browser-like headers are set

Keep this module lightweight and reusable across tasks.

IMPORTANT: Do not hardcode task-instance answers. Use these helpers to fetch
raw data, then write values into spreadsheets while keeping *calculations* as
Excel formulas.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Mapping


_IMF_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.imf.org/external/datamapper/",
    "Origin": "https://www.imf.org",
}


def urlopen_no_proxy(url: str, *, timeout: int = 60, headers: Mapping[str, str] | None = None) -> bytes:
    """Open a URL bypassing env proxy variables.

    This mirrors the pattern documented in SKILL.md, but centralizes it.
    """

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers=dict(headers or {}))
    with opener.open(req, timeout=timeout) as r:
        return r.read()


def get_json_no_proxy(url: str, *, timeout: int = 60, headers: Mapping[str, str] | None = None) -> Any:
    """Fetch JSON via urlopen_no_proxy."""

    raw = urlopen_no_proxy(url, timeout=timeout, headers=headers)
    return json.loads(raw.decode("utf-8", "ignore"))


def imf_datamapper_series(
    indicator: str,
    country: str,
    *,
    timeout: int = 60,
    headers: Mapping[str, str] | None = None,
) -> dict[int, float]:
    """Fetch an IMF DataMapper series as {year:int -> value:float}.

    Endpoint format:
      https://www.imf.org/external/datamapper/api/v1/<INDICATOR>/<COUNTRY>

    Notes:
    - Some invalid/unsupported indicators may return metadata without a
      `values` field. In that case we raise ValueError.
    """

    url = f"https://www.imf.org/external/datamapper/api/v1/{indicator}/{country}"
    hdr = dict(_IMF_BROWSER_HEADERS)
    if headers:
        hdr.update(dict(headers))

    data = get_json_no_proxy(url, timeout=timeout, headers=hdr)
    values = data.get("values")
    if not isinstance(values, dict) or indicator not in values:
        raise ValueError(
            "IMF DataMapper response did not include values for indicator "
            f"{indicator!r}."
        )

    series = values.get(indicator, {}).get(country)
    if not isinstance(series, dict):
        raise ValueError(
            "IMF DataMapper response did not include country series for "
            f"{indicator!r}/{country!r}."
        )

    out: dict[int, float] = {}
    for y, v in series.items():
        try:
            year = int(y)
        except Exception:
            continue
        if v is None:
            continue
        try:
            out[year] = float(v)
        except Exception:
            continue
    return out
