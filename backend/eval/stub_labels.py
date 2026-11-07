"""Append a label line for every capture not yet in labels.jsonl.

Run: uv run python -m eval.stub_labels
Then fill in brand, model, product_url, category and is_short for the new lines.
"""

import json

from app.config import EVAL_CAPTURES_DIR
from app.schemas import IdentifyRequest
from eval.labels import LABELS_PATH, read_labels


def main() -> None:
    labeled = {(label["video_id"], label["timestamp"]) for label in read_labels()}
    # Oldest first, so the dev subset ("first 50") is the first 50 captured.
    captures = sorted(EVAL_CAPTURES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    added = 0
    with LABELS_PATH.open("a") as labels:
        for path in captures:
            capture = IdentifyRequest.model_validate_json(path.read_text())
            # Same rounding as the capture file name, so labels find their capture.
            timestamp = float(f"{capture.t:.1f}")
            if (capture.video_id, timestamp) in labeled:
                continue
            stub = {
                "video_id": capture.video_id,
                "timestamp": timestamp,
                "brand": "",
                "model": "",
                "product_url": "",
                "category": "",
                "is_short": False,
                "title": capture.title,  # only to help you recognize the video
            }
            labels.write(json.dumps(stub) + "\n")
            added += 1
    print(f"Added {added} stub(s) to {LABELS_PATH}")


if __name__ == "__main__":
    main()
