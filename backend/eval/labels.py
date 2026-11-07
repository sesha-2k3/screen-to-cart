import json
from pathlib import Path
from typing import Any

from app.config import EVAL_CAPTURES_DIR

LABELS_PATH = Path(__file__).resolve().parent / "labels.jsonl"


def read_labels() -> list[dict[str, Any]]:
    if not LABELS_PATH.exists():
        return []
    lines = LABELS_PATH.read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def capture_path(video_id: str, timestamp: float) -> Path:
    # Same name the backend uses when SAVE_EVAL_CAPTURES is on.
    return EVAL_CAPTURES_DIR / f"{video_id}_{timestamp:.1f}.json"
