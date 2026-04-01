from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from voyah_pipeline.lang_detect import guess_lang_from_text
from voyah_pipeline.paths import extracted_dir, pdfs_dir, repo_root
from voyah_pipeline.schema_validate import validate_against
from voyah_pipeline.slug import pdf_stem_to_doc_id

EXTRACTOR_VERSION = "pymupdf-1.x+pipeline-1.0"
# Below this average chars/page, treat as likely scanned (flag OCR needed).
LOW_TEXT_THRESHOLD = 40


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_page_dict(page: fitz.Page, doc_id: str, page_number: int, images_dir: Path) -> dict[str, Any]:
    """Build page JSON with text blocks and embedded image extraction."""
    d = page.get_text("dict")
    blocks_out: list[dict[str, Any]] = []
    char_count = 0

    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines_text: list[str] = []
        max_size = 0.0
        bbox = block.get("bbox", [0, 0, 0, 0])
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            for sp in spans:
                t = sp.get("text", "") or ""
                lines_text.append(t)
                char_count += len(t)
                sz = float(sp.get("size", 0) or 0)
                max_size = max(max_size, sz)
        text = "".join(lines_text).strip()
        if text:
            blocks_out.append(
                {
                    "type": "text",
                    "text": text,
                    "bbox": [float(x) for x in bbox],
                    "font_size": max_size if max_size > 0 else None,
                    "image_ref": None,
                }
            )

    # Extract embedded images on page
    image_list = page.get_images(full=True)
    for _img_idx, img in enumerate(image_list):
        xref = img[0]
        try:
            base = page.parent.extract_image(xref)
        except Exception:
            continue
        img_bytes = base["image"]
        ext = base.get("ext", "png") or "png"
        h = hashlib.sha256(img_bytes).hexdigest()[:16]
        fname = f"{doc_id}-p{page_number:04d}-{h}.{ext}"
        out_path = images_dir / fname
        if not out_path.exists():
            out_path.write_bytes(img_bytes)
        blocks_out.append(
            {
                "type": "image",
                "text": f"[Image]({fname})",
                "bbox": [0, 0, 0, 0],
                "font_size": None,
                "image_ref": fname,
            }
        )

    text_joined = "\n\n".join(b["text"] for b in blocks_out if b["type"] == "text")
    page_json: dict[str, Any] = {
        "page_number": page_number,
        "width": float(page.rect.width),
        "height": float(page.rect.height),
        "blocks": blocks_out,
        "text_joined": text_joined,
        "char_count": char_count,
        "ocr_applied": False,
        "ocr_confidence_mean": None,
    }
    validate_against("page.schema.json", page_json)
    return page_json


def is_likely_scanned(pages: list[dict[str, Any]]) -> bool:
    if not pages:
        return True
    total_chars = sum(p["char_count"] for p in pages)
    avg = total_chars / len(pages)
    return avg < LOW_TEXT_THRESHOLD


def extract_pdf(pdf_path: Path, force: bool = False) -> dict[str, Any]:
    """Extract one PDF to src/raw/extracted/<doc_id>/. Returns document.json data."""
    rel = pdf_path.relative_to(repo_root())
    stem = pdf_path.stem
    doc_id = pdf_stem_to_doc_id(stem)
    sha = _sha256_file(pdf_path)

    base = extracted_dir() / doc_id
    pages_dir = base / "pages"
    images_dir = base / "images"
    ocr_dir = base / "ocr"
    pages_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    ocr_dir.mkdir(parents=True, exist_ok=True)

    doc_json_path = base / "document.json"
    manifest_path = extracted_dir() / "manifest.json"

    # Incremental skip
    if not force and doc_json_path.exists():
        try:
            existing = json.loads(doc_json_path.read_text(encoding="utf-8"))
            if existing.get("sha256") == sha:
                return existing
        except (json.JSONDecodeError, OSError):
            pass

    doc = fitz.open(pdf_path)
    pages_data: list[dict[str, Any]] = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            page_number = i + 1
            pjson = extract_page_dict(page, doc_id, page_number, images_dir)
            pages_data.append(pjson)
            (pages_dir / f"page-{page_number:04d}.json").write_text(
                json.dumps(pjson, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    finally:
        doc.close()

    full_text_sample = "\n".join(p["text_joined"] for p in pages_data[:3])[:8000]
    source_lang = guess_lang_from_text(full_text_sample)
    likely_scanned = is_likely_scanned(pages_data)

    if likely_scanned:
        note = {
            "status": "ocr_recommended",
            "reason": f"avg_chars_per_page_below_{LOW_TEXT_THRESHOLD}",
            "hint": "Install Tesseract and enable pytesseract in pipeline for OCR, or use OCRmyPDF.",
        }
        (ocr_dir / "status.json").write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")

    document = {
        "doc_id": doc_id,
        "source_pdf_path": str(rel).replace("\\", "/"),
        "sha256": sha,
        "source_lang": source_lang,
        "pages": len(pages_data),
        "extractor_version": EXTRACTOR_VERSION,
        "ocr_used": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title_hint": stem,
    }
    validate_against("document.schema.json", document)
    doc_json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _update_manifest(manifest_path, document, likely_scanned)
    return document


def _update_manifest(manifest_path: Path, document: dict[str, Any], likely_scanned: bool) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "doc_id": document["doc_id"],
        "source_pdf_relpath": document["source_pdf_path"],
        "sha256": document["sha256"],
        "source_lang": document["source_lang"],
        "last_extracted_at": document["created_at"],
        "ocr_used": document["ocr_used"],
        "extractor_version": document["extractor_version"],
    }
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"version": "1", "updated_at": "", "documents": []}
    else:
        data = {"version": "1", "updated_at": "", "documents": []}

    docs = [d for d in data.get("documents", []) if d.get("doc_id") != entry["doc_id"]]
    docs.append(entry)
    data["documents"] = sorted(docs, key=lambda x: x["doc_id"])
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if likely_scanned:
        # informational only in index
        pass
    validate_against("manifest.schema.json", data)
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_all(force: bool = False) -> list[dict[str, Any]]:
    pdfs = sorted(pdfs_dir().glob("*.pdf"))
    results: list[dict[str, Any]] = []
    for p in pdfs:
        results.append(extract_pdf(p, force=force))
    return results
