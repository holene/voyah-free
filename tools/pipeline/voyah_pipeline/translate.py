from __future__ import annotations

import json
from typing import Any

from voyah_pipeline.llm import chat_json, llm_available
from voyah_pipeline.paths import extracted_dir, glossary_path, normalized_dir
from voyah_pipeline.schema_validate import validate_against


def _target_lang(source: str) -> str:
    return "no" if source == "en" else "en"


def _load_glossary() -> dict[str, Any]:
    p = glossary_path()
    if not p.exists():
        return {"version": "0", "terms": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def translate_canonical(doc_id: str) -> dict[str, Any] | None:
    """Produce translated.<target>.json when LLM is available; else return None."""
    nd = normalized_dir() / doc_id
    if not nd.exists():
        return None

    canon_files = list(nd.glob("canonical.*.json"))
    if not canon_files:
        return None
    cf = canon_files[0]
    canonical = json.loads(cf.read_text(encoding="utf-8"))
    src_lang = canonical["lang"]
    tgt_lang = _target_lang(src_lang)

    terminology_version = _load_glossary().get("version", "1")
    translation_model = "none"
    qa_flags: list[str] = []

    if not llm_available():
        return None

    glossary = _load_glossary()
    system = (
        f"Translate technical documentation from {src_lang} to {tgt_lang}. "
        "Return a JSON object matching the input shape: "
        "title, description, lang (target), sections (same ids and chunk_ids), "
        "warnings, specs (translate label only; keep value identical if numeric), "
        "glossary_terms (array of term keys used), provenance (copy unchanged). "
        "Preserve ALL numbers, units, model names, and paths exactly. "
        "Use Markdown in body_md. Apply glossary hints when present."
    )
    user = json.dumps({"glossary": glossary, "canonical": canonical}, ensure_ascii=False)[:120000]
    try:
        data = chat_json(system, user)
        merged = data.get("translation") or data
        translation_model = __import__("os").environ.get("PIPELINE_LLM_MODEL", "gpt-4o-mini")
    except Exception as e:
        qa_flags.append(f"translation_error:{type(e).__name__}")
        (nd / f"translated.{tgt_lang}.error.json").write_text(
            json.dumps({"error": str(e)}, indent=2) + "\n", encoding="utf-8"
        )
        return None

    out: dict[str, Any] = {
        "doc_id": doc_id,
        "title": merged.get("title", canonical["title"]),
        "description": merged.get("description", canonical["description"]),
        "lang": tgt_lang,
        "sections": merged.get("sections", canonical["sections"]),
        "warnings": merged.get("warnings", canonical["warnings"]),
        "specs": merged.get("specs", canonical["specs"]),
        "glossary_terms": merged.get("glossary_terms", canonical.get("glossary_terms", [])),
        "provenance": canonical["provenance"],
        "source_lang": src_lang,
        "translation_model": translation_model,
        "terminology_version": str(terminology_version),
        "qa_flags": qa_flags,
    }

    # Ensure section ids match
    c_ids = [s["id"] for s in canonical["sections"]]
    t_ids = [s["id"] for s in out["sections"]]
    if c_ids != t_ids:
        qa_flags.append("section_id_mismatch_reverted")
        out["sections"] = canonical["sections"]
        out["qa_flags"] = qa_flags

    validate_against("translation-doc.schema.json", out)
    (nd / f"translated.{tgt_lang}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    return out


def _clear_stale_translations() -> None:
    root = normalized_dir()
    if not root.exists():
        return
    for nd in root.iterdir():
        if not nd.is_dir():
            continue
        for p in nd.glob("translated.*.json"):
            p.unlink(missing_ok=True)
        for p in nd.glob("translated.*.error.json"):
            p.unlink(missing_ok=True)


def translate_all_from_manifest() -> None:
    manifest_path = extracted_dir() / "manifest.json"
    if not manifest_path.exists():
        return
    _clear_stale_translations()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in data.get("documents", []):
        translate_canonical(entry["doc_id"])
