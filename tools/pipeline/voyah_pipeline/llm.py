from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def llm_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("PIPELINE_LLM_API_KEY"))


def _api_key() -> str:
    return os.environ.get("PIPELINE_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


def _base_url() -> str:
    return os.environ.get("PIPELINE_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def _model() -> str:
    return os.environ.get("PIPELINE_LLM_MODEL", "gpt-4o-mini")


def chat_json(system: str, user: str, timeout_s: float = 120.0) -> dict[str, Any]:
    """Call OpenAI-compatible chat completions API; parse JSON object from message content."""
    key = _api_key()
    if not key:
        raise RuntimeError("No API key set")

    payload = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{_base_url()}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode("utf-8", errors="replace")) from e

    content = body["choices"][0]["message"]["content"]
    return json.loads(content)
