"""Stored LLM responses for LLM_MODE=record and replay. Files never contain the image."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from langchain_core.messages import BaseMessage

# backend/app/llm/fixtures.py -> parents[3] is the repo root.
FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "llm"


def fixture_key(model_spec: str, messages: list[BaseMessage]) -> str:
    """Hash of the model and the exact messages, image included, so any change misses."""
    payload = [model_spec, [(message.type, message.content) for message in messages]]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def read_fixture(key: str) -> str | None:
    path = FIXTURES_DIR / f"{key}.json"
    if not path.exists():
        return None
    content: str = json.loads(path.read_text())["content"]
    return content


def write_fixture(
    key: str, role: str, model_spec: str, prompt_version: str, content: str
) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "role": role,
        "model": model_spec,
        "prompt_version": prompt_version,
        "content": content,
    }
    (FIXTURES_DIR / f"{key}.json").write_text(json.dumps(record, indent=2) + "\n")
