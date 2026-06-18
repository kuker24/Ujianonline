"""Shared helpers for safe export responses."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote


_NON_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_SEPARATORS = re.compile(r"[_-]{2,}")


def safe_ascii_filename(filename: str, *, fallback: str = "export") -> str:
    """Return a conservative ASCII filename for legacy Content-Disposition clients."""
    raw = str(filename or "").strip()
    if not raw:
        raw = fallback

    normalized = unicodedata.normalize("NFKD", raw)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.replace("/", "_").replace("\\", "_")
    ascii_name = _NON_FILENAME_CHARS.sub("_", ascii_name)
    ascii_name = _REPEATED_SEPARATORS.sub("_", ascii_name)
    ascii_name = re.sub(r"_+(\.[A-Za-z0-9]+)$", r"\1", ascii_name)
    ascii_name = ascii_name.strip("._- ")
    return ascii_name or fallback


def content_disposition_attachment(filename: str, *, fallback: str = "export") -> str:
    """Build RFC5987-compatible attachment Content-Disposition.

    Includes an ASCII ``filename`` fallback plus UTF-8 ``filename*`` for modern
    browsers. The raw filename is never inserted directly into the header.
    """
    ascii_name = safe_ascii_filename(filename, fallback=fallback)
    utf8_name = quote(str(filename or fallback), safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"


def attachment_headers(
    filename: str,
    *,
    fallback: str = "export",
    cache_control: str | None = None,
) -> dict[str, str]:
    """Return safe attachment headers for export responses."""
    headers = {
        "Content-Disposition": content_disposition_attachment(filename, fallback=fallback),
    }
    if cache_control:
        headers["Cache-Control"] = cache_control
    return headers
