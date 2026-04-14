"""Public-domain FRED CSV fetcher — no API key required.

FRED (Federal Reserve Economic Data) exposes CSV downloads for
every series at a stable URL:

    https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>

These are public-domain under US government work. No authentication,
no subscription. This module uses only the Python standard library
(``urllib``) to avoid adding a runtime dependency for what is a
single HTTPS GET.

Design invariants
-----------------

* Deterministic: same series, same day → same bytes (modulo any FRED
  revision; revisions are rare on historical series).
* Fail-closed: network failures raise, never produce a fake dataset.
* Provenance: every fetch records the URL, bytes hash (sha256),
  fetch timestamp, and last-modified header if present.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import io
import pathlib
import urllib.request

__all__ = [
    "FREDFetch",
    "fetch_series",
    "fred_csv_url",
]

_FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_USER_AGENT = "NeoSynaptex-gamma-program/1.0 (+neuron7xLab/neosynaptex)"


def fred_csv_url(series_id: str) -> str:
    """Return the canonical public CSV URL for a FRED series."""

    return f"{_FRED_BASE}?id={series_id}"


@dataclasses.dataclass(frozen=True)
class FREDFetch:
    """Record of one FRED CSV fetch — full provenance."""

    series_id: str
    url: str
    bytes_count: int
    sha256: str
    fetched_utc: str
    last_modified_header: str | None
    content_type: str | None
    raw_csv: bytes

    def as_provenance_dict(self) -> dict:
        """Return serialisable provenance (no raw bytes)."""

        return {
            "series_id": self.series_id,
            "url": self.url,
            "bytes_count": self.bytes_count,
            "sha256": self.sha256,
            "fetched_utc": self.fetched_utc,
            "last_modified_header": self.last_modified_header,
            "content_type": self.content_type,
        }


def fetch_series(
    series_id: str,
    *,
    timeout_s: float = 30.0,
    out_path: pathlib.Path | None = None,
) -> FREDFetch:
    """Fetch one FRED series CSV. Raises on network/HTTP failure.

    Parameters
    ----------
    series_id:
        FRED series identifier, e.g. ``"INDPRO"``, ``"T10Y2Y"``.
    timeout_s:
        Request timeout in seconds. Default 30s.
    out_path:
        If given, write the raw CSV bytes to this path after fetch.

    Returns
    -------
    FREDFetch with full provenance. ``raw_csv`` contains the bytes
    so the caller can parse with any CSV reader (pandas, stdlib,
    etc.).
    """

    url = fred_csv_url(series_id)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
        last_mod = resp.headers.get("Last-Modified")
        content_type = resp.headers.get("Content-Type")

    sha = hashlib.sha256(raw).hexdigest()
    fetched = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    if out_path is not None:
        out_path = pathlib.Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(raw)

    return FREDFetch(
        series_id=series_id,
        url=url,
        bytes_count=len(raw),
        sha256=sha,
        fetched_utc=fetched,
        last_modified_header=last_mod,
        content_type=content_type,
        raw_csv=raw,
    )


def parse_fred_csv(raw: bytes) -> list[tuple[str, float | None]]:
    """Parse a FRED CSV payload into a list of (date, value) pairs.

    Returns ``None`` for the value when the row is marked ``"."`` by
    FRED (its sentinel for missing data). Dates are left as strings;
    the caller converts if needed.
    """

    rows: list[tuple[str, float | None]] = []
    text = raw.decode("utf-8")
    reader = iter(io.StringIO(text))
    header = next(reader, None)
    if header is None:
        raise ValueError("empty FRED CSV payload")
    # FRED header is "DATE,<SERIES_ID>" — we don't need to parse it.
    for line in reader:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) != 2:
            continue
        date, val = parts
        if val == "." or val == "":
            rows.append((date, None))
        else:
            try:
                rows.append((date, float(val)))
            except ValueError:
                rows.append((date, None))
    return rows
