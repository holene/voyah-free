from __future__ import annotations

import re
import unicodedata


def pdf_stem_to_doc_id(stem: str) -> str:
    """Stable slug: lowercase, ascii-ish, hyphenated."""
    s = unicodedata.normalize("NFKD", stem)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    if not s:
        s = "document"
    if not re.match(r"^[a-z0-9]", s):
        s = "d-" + s
    return s[:80]
