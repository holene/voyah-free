from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from voyah_pipeline.paths import extracted_dir
from voyah_pipeline.schema_validate import validate_against


HEADING_FONT_MIN = 13.0
MAX_CHUNK_CHARS = 6000


def _chunk_fingerprint(doc_id: str, page_start: int, page_end: int, text: str) -> str:
    raw = f"{doc_id}|{page_start}|{page_end}|{text[:240]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _looks_like_table(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    tab = sum(1 for ln in lines if "\t" in ln or ln.count("  ") >= 3)
    return tab >= 2


def build_chunks_for_doc(doc_id: str) -> list[dict[str, Any]]:
    base = extracted_dir() / doc_id
    doc_path = base / "document.json"
    if not doc_path.exists():
        raise FileNotFoundError(doc_path)
    pages_dir = base / "pages"
    page_files = sorted(pages_dir.glob("page-*.json"))
    chunks_dir = base / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[dict[str, Any]] = []
    cur_text: list[str] = []
    cur_pages: list[int] = []
    cur_heading: str | None = None
    cur_image_refs: list[str] = []

    def flush() -> None:
        nonlocal cur_text, cur_pages, cur_heading, cur_image_refs
        if not cur_pages:
            return
        text = "\n\n".join(t for t in cur_text if t.strip()).strip()
        if not text and not cur_image_refs:
            cur_text = []
            cur_pages = []
            cur_heading = None
            cur_image_refs = []
            return
        ps, pe = min(cur_pages), max(cur_pages)
        chunk_id = _chunk_fingerprint(doc_id, ps, pe, text or ",".join(cur_image_refs))
        chunk = {
            "chunk_id": chunk_id,
            "page_start": ps,
            "page_end": pe,
            "text": text or "[images only]",
            "heading_hint": cur_heading,
            "table_hint": _looks_like_table(text),
            "image_refs": list(dict.fromkeys(cur_image_refs)),
            "confidence": 0.85 if text else 0.5,
        }
        validate_against("chunk.schema.json", chunk)
        chunks.append(chunk)
        out = chunks_dir / f"chunk-{chunk_id}.json"
        out.write_text(json.dumps(chunk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cur_text = []
        cur_pages = []
        cur_heading = None
        cur_image_refs = []

    for pf in page_files:
        page = json.loads(pf.read_text(encoding="utf-8"))
        pnum = page["page_number"]
        for block in page.get("blocks", []):
            if block["type"] == "image" and block.get("image_ref"):
                cur_image_refs.append(block["image_ref"])
                if pnum not in cur_pages:
                    cur_pages.append(pnum)
                continue
            if block["type"] != "text":
                continue
            t = block.get("text") or ""
            fs = block.get("font_size")
            is_heading = fs is not None and float(fs) >= HEADING_FONT_MIN and len(t) < 120 and "\n" not in t
            if is_heading and cur_text:
                flush()
            if is_heading:
                cur_heading = t.strip()
            if pnum not in cur_pages:
                cur_pages.append(pnum)
            cur_text.append(t)
            joined = "\n\n".join(cur_text)
            if len(joined) >= MAX_CHUNK_CHARS:
                flush()
        # page boundary soft break: flush if chunk spans many pages
        if cur_pages and max(cur_pages) != pnum:
            pass
        joined = "\n\n".join(cur_text)
        if len(joined) >= MAX_CHUNK_CHARS:
            flush()

    flush()

    # If no chunks (empty PDF), emit one placeholder
    if not chunks:
        chunk = {
            "chunk_id": _chunk_fingerprint(doc_id, 1, 1, "empty"),
            "page_start": 1,
            "page_end": 1,
            "text": "[No extractable text]",
            "heading_hint": None,
            "table_hint": False,
            "image_refs": [],
            "confidence": 0.1,
        }
        validate_against("chunk.schema.json", chunk)
        chunks.append(chunk)
        (chunks_dir / f"chunk-{chunk['chunk_id']}.json").write_text(
            json.dumps(chunk, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return chunks


def chunk_all_from_manifest() -> None:
    manifest = extracted_dir() / "manifest.json"
    if not manifest.exists():
        return
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for entry in data.get("documents", []):
        build_chunks_for_doc(entry["doc_id"])
