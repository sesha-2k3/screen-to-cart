"""See or delete eval captures.

Run: uv run python -m eval.review              writes captures/review.html, open it in a browser
     uv run python -m eval.review --delete ID   deletes captures/ID.json and its label line
"""

import argparse
import json
from html import escape
from pathlib import Path

from app.config import EVAL_CAPTURES_DIR, get_settings
from app.graph.prompts import tier1_messages, tier2_messages
from app.llm.factory import Role
from app.llm.fixtures import fixture_key, read_fixture
from app.schemas import Candidates, IdentifyRequest
from eval.labels import LABELS_PATH, read_labels

REVIEW_PATH = EVAL_CAPTURES_DIR / "review.html"


def stored_answers(
    capture: IdentifyRequest,
) -> tuple[Candidates | None, Candidates | None]:
    """Tier 1 and Tier 2 responses recorded for this capture, if any."""
    settings = get_settings()
    context = (capture.title, capture.description, capture.transcript)
    tier1_spec = settings.model_spec_for(Role.IDENTIFY_VISION) or ""
    stored = read_fixture(
        fixture_key(tier1_spec, tier1_messages(capture.frames[0], *context))
    )
    if stored is None:
        return None, None
    tier1 = Candidates.model_validate_json(stored)
    tier2_spec = settings.model_spec_for(Role.DISAMBIGUATE) or ""
    stored = read_fixture(fixture_key(tier2_spec, tier2_messages(tier1, *context)))
    return tier1, Candidates.model_validate_json(stored) if stored else None


def describe(answer: Candidates | None) -> str:
    if answer is None:
        return "not run"
    if not answer.candidates:
        return "no product found"
    return ", ".join(
        f"{c.brand} {c.model} ({c.confidence:.0%})" for c in answer.candidates
    )


def card(path: Path, labels: dict[tuple[str, float], dict[str, str]]) -> str:
    capture = IdentifyRequest.model_validate_json(path.read_text())
    tier1, tier2 = stored_answers(capture)
    label = labels.get((capture.video_id, float(f"{capture.t:.1f}")))
    labeled = f"{label['brand']} {label['model']}".strip() if label else ""
    url = f"https://www.youtube.com/watch?v={capture.video_id}&t={int(capture.t)}s"
    return f"""
<article>
  <img src="data:image/jpeg;base64,{capture.frames[0]}">
  <div>
    <h2>{escape(capture.title)}</h2>
    <p><a href="{url}" target="_blank">Open at {int(capture.t // 60)}:{int(capture.t % 60):02d}</a>
       · delete: <code>uv run python -m eval.review --delete {path.stem}</code></p>
    <p><b>Tier 1:</b> {escape(describe(tier1))}</p>
    <p><b>Tier 2:</b> {escape(describe(tier2))}</p>
    <p><b>Label:</b> {escape(labeled) or "<i>not labeled yet</i>"}</p>
  </div>
</article>"""


def write_review() -> None:
    labels = {(item["video_id"], item["timestamp"]): item for item in read_labels()}
    captures = sorted(EVAL_CAPTURES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    cards = "".join(card(path, labels) for path in captures)
    REVIEW_PATH.write_text(f"""<!doctype html>
<meta charset="utf-8"><title>Eval captures ({len(captures)})</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 1000px; margin: 2rem auto; }}
  article {{ display: flex; gap: 1rem; border-bottom: 1px solid #ddd; padding: 1rem 0; }}
  img {{ width: 360px; max-height: 360px; object-fit: contain; background: #000; }}
  h2 {{ font-size: 1.1rem; margin-top: 0; }}
</style>
<h1>Eval captures ({len(captures)})</h1>{cards}
""")
    print(f"Open {REVIEW_PATH}")


def delete(capture_id: str) -> None:
    path = EVAL_CAPTURES_DIR / f"{capture_id}.json"
    capture = IdentifyRequest.model_validate_json(path.read_text())
    key = (capture.video_id, float(f"{capture.t:.1f}"))
    kept = [
        item for item in read_labels() if (item["video_id"], item["timestamp"]) != key
    ]
    if LABELS_PATH.exists():
        LABELS_PATH.write_text("".join(json.dumps(item) + "\n" for item in kept))
    path.unlink()
    print(f"Deleted {path.name} and its label line, if any")
    write_review()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delete", metavar="ID", help="capture file name without .json"
    )
    args = parser.parse_args()
    if args.delete:
        delete(args.delete)
    else:
        write_review()
