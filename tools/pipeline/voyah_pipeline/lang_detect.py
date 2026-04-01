from __future__ import annotations

import re


_NO_HINTS = re.compile(
    r"\b(og|eller|ikke|med|fra|til|den|det|som|vær|kjør|skjerm|bil|modus)\b",
    re.IGNORECASE,
)


def guess_lang_from_text(sample: str) -> str:
    """Rough en/no guess from extracted text (per-PDF canonical)."""
    if not sample or not sample.strip():
        return "en"
    nordic = len(re.findall(r"[æøåÆØÅ]", sample))
    ratio = nordic / max(len(sample), 1)
    if ratio > 0.002 or _NO_HINTS.search(sample):
        return "no"
    return "en"
