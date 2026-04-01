from __future__ import annotations

import json
import re
from typing import Any

from voyah_pipeline.paths import normalized_dir, repo_root
from voyah_pipeline.schema_validate import validate_against


SAFETY_PATTERNS = re.compile(
    r"\b(ADAS|autopilot|autonomous|emergency brake|collision|airbag|recall|charging cable|high voltage)\b",
    re.IGNORECASE,
)


def _extract_numbers(text: str) -> list[str]:
    return re.findall(
        r"\b\d+(?:[.,]\d+)?\s*(?:kW|kWh|Nm|km/h|km|mm|kW|V|A|%|°C)?\b|\b\d+(?:[.,]\d+)?\b",
        text,
    )


def qa_canonical(doc_id: str) -> list[str]:
    flags: list[str] = []
    nd = normalized_dir() / doc_id
    cfiles = list(nd.glob("canonical.*.json"))
    if not cfiles:
        flags.append("missing_canonical")
        return flags
    canonical = json.loads(cfiles[0].read_text(encoding="utf-8"))
    try:
        validate_against("canonical-doc.schema.json", canonical)
    except Exception as e:
        flags.append(f"canonical_schema:{e}")

    blob = json.dumps(canonical, ensure_ascii=False)
    if SAFETY_PATTERNS.search(blob):
        flags.append("manual_review_safety_related_content")

    if not canonical.get("sections"):
        flags.append("empty_sections")

    for s in canonical.get("sections", []):
        if not (s.get("body_md") or "").strip() or s["body_md"].strip() == "_No body extracted._":
            flags.append(f"thin_section:{s.get('id')}")

    return flags


def qa_translation_pair(doc_id: str) -> list[str]:
    flags: list[str] = []
    nd = normalized_dir() / doc_id
    cfiles = list(nd.glob("canonical.*.json"))
    tfiles = list(nd.glob("translated.*.json"))
    if not cfiles:
        return ["missing_canonical"]
    canonical = json.loads(cfiles[0].read_text(encoding="utf-8"))
    # Skip placeholder files
    tpath = next((p for p in tfiles if not p.name.endswith(".error.json")), None)
    if not tpath:
        return ["no_translation_file"]
    try:
        trans = json.loads(tpath.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["translation_json_invalid"]
    if "sections" not in trans:
        return ["translation_skipped"]

    try:
        validate_against("translation-doc.schema.json", trans)
    except Exception as e:
        flags.append(f"translation_schema:{e}")
        return flags

    c_nums = _extract_numbers(json.dumps(canonical.get("specs", [])))
    t_nums = _extract_numbers(json.dumps(trans.get("specs", [])))
    if c_nums != t_nums:
        flags.append("spec_numeric_mismatch")

    c_body_nums = _extract_numbers("".join(s.get("body_md", "") for s in canonical.get("sections", [])))
    t_body_nums = _extract_numbers("".join(s.get("body_md", "") for s in trans.get("sections", [])))
    if sorted(set(c_body_nums)) != sorted(set(t_body_nums)):
        flags.append("body_numeric_mismatch")

    return flags


def qa_report_all() -> dict[str, Any]:
    root = repo_root()
    manifest = root / "src" / "raw" / "extracted" / "manifest.json"
    if not manifest.exists():
        return {"documents": [], "error": "no_manifest"}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    reports: list[dict[str, Any]] = []
    for entry in data.get("documents", []):
        did = entry["doc_id"]
        c_flags = qa_canonical(did)
        t_flags = qa_translation_pair(did)
        reports.append(
            {
                "doc_id": did,
                "canonical_flags": c_flags,
                "translation_flags": t_flags,
            }
        )
    out = {"documents": reports}
    out_path = root / "src" / "raw" / "extracted" / "qa-report.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def qa_fail_on_errors(strict: bool = True) -> int:
    """Exit code 1 if strict and any schema errors."""
    rep = qa_report_all()
    bad = False
    for d in rep.get("documents", []):
        for f in d["canonical_flags"]:
            if f.startswith("canonical_schema"):
                bad = True
        for f in d["translation_flags"]:
            if f.startswith("translation_schema"):
                bad = True
    return 1 if strict and bad else 0
