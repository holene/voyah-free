from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from voyah_pipeline.extract import extract_all
from voyah_pipeline.chunking import build_chunks_for_doc, chunk_all_from_manifest
from voyah_pipeline.llm import chat_json, llm_available
from voyah_pipeline.paths import extracted_dir, normalized_dir
from voyah_pipeline.schema_validate import validate_against


def _slug_section_id(heading: str | None, chunk_id: str, index: int) -> str:
    base = heading or f"section-{index}"
    s = base.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s:
        s = f"chunk-{chunk_id[:8]}"
    return s[:60]


def _text_to_md_body(text: str) -> str:
    """Turn plain extracted text into conservative Markdown."""
    text = text.strip()
    if not text:
        return ""
    paragraphs = re.split(r"\n\s*\n", text)
    parts: list[str] = []
    for p in paragraphs:
        lines = [ln.rstrip() for ln in p.splitlines()]
        if all(ln.lstrip().startswith(("- ", "* ", "• ")) for ln in lines if ln.strip()):
            for ln in lines:
                if not ln.strip():
                    continue
                parts.append("- " + re.sub(r"^[-*•]\s*", "", ln.strip()))
            parts.append("")
        else:
            parts.append(" ".join(lines).strip())
            parts.append("")
    return "\n".join(parts).strip()


def build_canonical_deterministic(doc_id: str) -> dict[str, Any]:
    base = extracted_dir() / doc_id
    doc = json.loads((base / "document.json").read_text(encoding="utf-8"))
    chunk_files = sorted((base / "chunks").glob("chunk-*.json"))
    chunks = [json.loads(p.read_text(encoding="utf-8")) for p in chunk_files]

    sections: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    def _unique_section_id(base_id: str) -> str:
        uid = base_id
        n = 0
        while uid in used_ids:
            n += 1
            uid = f"{base_id}-{n}"
        used_ids.add(uid)
        return uid

    for i, ch in enumerate(chunks):
        hid = _unique_section_id(_slug_section_id(ch.get("heading_hint"), ch["chunk_id"], i))
        level = 2 if ch.get("heading_hint") else 2
        heading = ch.get("heading_hint") or f"Section {i + 1}"
        body = _text_to_md_body(ch["text"])
        img_lines = []
        for ref in ch.get("image_refs") or []:
            img_lines.append(f"![Figure](/from-pdf/{doc_id}/{ref})")
        if img_lines:
            body = (body + "\n\n" if body else "") + "\n\n".join(img_lines)
        sections.append(
            {
                "id": hid,
                "heading": heading,
                "level": level,
                "body_md": body or "_No body extracted._",
                "chunk_ids": [ch["chunk_id"]],
            }
        )

    title = doc.get("title_hint") or (sections[0]["heading"] if sections else doc_id)
    desc = f"Imported from PDF ({doc['source_lang'].upper()}). {title[:120]}"

    canonical: dict[str, Any] = {
        "doc_id": doc_id,
        "title": str(title)[:200],
        "description": desc[:300],
        "lang": doc["source_lang"],
        "sections": sections,
        "warnings": [],
        "specs": [],
        "glossary_terms": [],
        "provenance": [
            {
                "source_pdf": doc["source_pdf_path"],
                "page_start": 1,
                "page_end": doc["pages"],
                "sha256": doc["sha256"],
            }
        ],
    }

    if llm_available() and __import__("os").environ.get("PIPELINE_LLM_CANONICAL") == "1":
        canonical = _llm_polish_canonical(canonical, chunks)

    validate_against("canonical-doc.schema.json", canonical)
    out_dir = normalized_dir() / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)
    lang = canonical["lang"]
    (out_dir / f"canonical.{lang}.json").write_text(
        json.dumps(canonical, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return canonical


def _llm_polish_canonical(canonical: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    system = (
        "You improve technical documentation Markdown for clarity without changing facts. "
        "Return JSON with keys: title (string), description (string), sections (array of objects "
        "with id, heading, level, body_md, chunk_ids). Preserve every id and chunk_ids exactly. "
        "Do not invent specifications. Keep numbers and units identical."
    )
    user = json.dumps({"canonical": canonical, "chunks": chunks}, ensure_ascii=False)[:120000]
    try:
        data = chat_json(system, user)
        merged = data.get("canonical") or data
        if not isinstance(merged, dict):
            return canonical
        # Require same section ids set
        old_ids = {s["id"] for s in canonical["sections"]}
        new_secs = merged.get("sections")
        if not new_secs or {s.get("id") for s in new_secs} != old_ids:
            return canonical
        canonical["title"] = merged.get("title", canonical["title"])
        canonical["description"] = merged.get("description", canonical["description"])
        for s in canonical["sections"]:
            match = next((x for x in new_secs if x.get("id") == s["id"]), None)
            if match and match.get("body_md"):
                s["heading"] = match.get("heading", s["heading"])
                s["level"] = int(match.get("level", s["level"]))
                s["body_md"] = match["body_md"]
        return canonical
    except Exception:
        return canonical


def canonicalize_all() -> list[dict[str, Any]]:
    extract_all(force=False)
    chunk_all_from_manifest()
    manifest = extracted_dir() / "manifest.json"
    if not manifest.exists():
        return []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for entry in data.get("documents", []):
        out.append(build_canonical_deterministic(entry["doc_id"]))
    return out
