from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from voyah_pipeline.paths import extracted_dir, normalized_dir, public_generated_images, repo_root
from voyah_pipeline.schema_validate import validate_against


def _docs_path_for_lang(lang: str) -> Path:
    base = repo_root() / "src" / "content" / "docs"
    if lang == "en":
        return base / "from-sources"
    return base / "no" / "from-sources"


def _copy_images(doc_id: str) -> None:
    src = extracted_dir() / doc_id / "images"
    if not src.exists():
        return
    dest = public_generated_images() / doc_id
    dest.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, dest / f.name)


def _frontmatter(title: str, description: str, extra: dict[str, Any] | None = None) -> str:
    lines = ["---", f'title: "{_escape_yaml(title)}"', f'description: "{_escape_yaml(description)}"']
    if extra:
        for k, v in extra.items():
            lines.append(f"{k}: {json.dumps(v)}")
    lines.append("---\n")
    return "\n".join(lines)


def _escape_yaml(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _render_body(canonical: dict[str, Any]) -> str:
    parts: list[str] = []
    for sec in canonical.get("sections", []):
        level = int(sec.get("level", 2))
        level = max(2, min(level, 6))
        hashes = "#" * level
        parts.append(f"{hashes} {sec.get('heading', 'Section')}\n\n{sec.get('body_md', '').strip()}\n")
    prov = canonical.get("provenance", [])
    if prov:
        parts.append("\n## Source\n\n")
        for p in prov:
            sha = p.get("sha256", "")
            parts.append(
                f"- PDF: `{p.get('source_pdf')}` (pages {p.get('page_start')}–{p.get('page_end')})"
                + (f", SHA-256: `{sha[:16]}…`" if sha else "")
                + "\n"
            )
    return "\n".join(parts).strip() + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_valid_translation(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    if "note" in obj and "skipped" in str(obj.get("note", "")).lower():
        return False
    return "sections" in obj and "translation_model" in obj and "source_lang" in obj


def render_doc(doc_id: str) -> list[Path]:
    """Write MDX for canonical and optional translation; copy images to public/."""
    _copy_images(doc_id)
    nd = normalized_dir() / doc_id
    cfiles = sorted(nd.glob("canonical.*.json"))
    if not cfiles:
        return []

    canonical = _load_json(cfiles[0])
    validate_against("canonical-doc.schema.json", canonical)

    written: list[Path] = []
    lang = canonical["lang"]
    out_dir = _docs_path_for_lang(lang)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_id}.mdx"
    body = _render_body(canonical)
    out_path.write_text(
        _frontmatter(canonical["title"], canonical["description"]) + "\n" + body,
        encoding="utf-8",
    )
    written.append(out_path)

    tgt_lang = "no" if lang == "en" else "en"
    tpath = nd / f"translated.{tgt_lang}.json"
    if tpath.exists():
        trans = _load_json(tpath)
        if is_valid_translation(trans):
            try:
                validate_against("translation-doc.schema.json", trans)
            except Exception:
                return written
            t_out = _docs_path_for_lang(tgt_lang)
            t_out.mkdir(parents=True, exist_ok=True)
            tp = t_out / f"{doc_id}.mdx"
            tp.write_text(
                _frontmatter(trans["title"], trans["description"]) + "\n" + _render_body(trans),
                encoding="utf-8",
            )
            written.append(tp)

    return written


def _clear_doc_mdx_except_index(folder: Path) -> None:
    if not folder.exists():
        return
    for f in folder.glob("*.mdx"):
        if f.name != "index.mdx":
            f.unlink()


def render_all_from_manifest() -> list[Path]:
    manifest = extracted_dir() / "manifest.json"
    if not manifest.exists():
        return []
    # Avoid stale pages when PDF set or translations change
    _clear_doc_mdx_except_index(_docs_path_for_lang("en"))
    _clear_doc_mdx_except_index(_docs_path_for_lang("no"))
    data = _load_json(manifest)
    paths: list[Path] = []
    for entry in data.get("documents", []):
        paths.extend(render_doc(entry["doc_id"]))
    return paths


def write_generated_index_stub() -> None:
    """Ensure Starlight autogenerate has an index for from-sources (root)."""
    root_fs = _docs_path_for_lang("en")
    root_fs.mkdir(parents=True, exist_ok=True)
    idx = root_fs / "index.mdx"
    if not idx.exists():
        idx.write_text(
            "---\n"
            'title: "From PDF sources"\n'
            'description: "Pages generated from src/raw/pdfs via the docs pipeline."\n'
            "---\n\n"
            "This section is produced by `tools/pipeline`. "
            "Each page lists its source PDF and page range in a **Source** section.\n",
            encoding="utf-8",
        )
    no_fs = _docs_path_for_lang("no")
    no_fs.mkdir(parents=True, exist_ok=True)
    idx_no = no_fs / "index.mdx"
    if not idx_no.exists():
        idx_no.write_text(
            "---\n"
            'title: "Importert fra PDF"\n'
            'description: "Sider generert fra PDF-kilder."\n'
            "---\n\n"
            "Disse sidene er generert av dokumentasjonspipelinen.\n",
            encoding="utf-8",
        )
