from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from voyah_pipeline.paths import schemas_dir


def _load(name: str) -> dict[str, Any]:
    p = schemas_dir() / name
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def validate_against(name: str, instance: Any) -> None:
    """Validate instance against a schema file in schemas/."""
    schema = _load(name)
    Draft202012Validator(schema).validate(instance)
