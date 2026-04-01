from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """tools/pipeline/voyah_pipeline/paths.py -> repo root."""
    return Path(__file__).resolve().parents[3]


def schemas_dir() -> Path:
    return repo_root() / "tools" / "pipeline" / "schemas"


def pdfs_dir() -> Path:
    return repo_root() / "src" / "raw" / "pdfs"


def extracted_dir() -> Path:
    return repo_root() / "src" / "raw" / "extracted"


def normalized_dir() -> Path:
    return repo_root() / "src" / "raw" / "normalized"


def glossary_path() -> Path:
    return repo_root() / "tools" / "pipeline" / "voyah_pipeline" / "glossary.json"


def public_generated_images() -> Path:
    return repo_root() / "public" / "from-pdf"
