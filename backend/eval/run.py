"""Tier 1 and Tier 1+2 accuracy on the labeled captures.

Run: uv run python -m eval.run --subset dev
Runs in LLM_MODE=record, so items whose responses are already stored cost no tokens.
"""

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import groq
from pydantic import ValidationError

from app.config import get_settings
from app.graph.build import build_graph
from app.graph.prompts import PROMPT_VERSION
from app.graph.state import PipelineState
from app.llm.factory import LlmConfigError, Role
from app.llm.invoke import FixtureMissingError, LlmOutputError
from app.llm.rate_limit import RateLimited
from app.schemas import IdentifyRequest, ProductCandidate
from eval.labels import capture_path, read_labels
from eval.metrics import top1_correct

DEV_SUBSET_SIZE = 50
MAX_ATTEMPTS = 3
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
ITEM_ERRORS = (
    LlmOutputError,
    FixtureMissingError,
    LlmConfigError,
    groq.APIError,
    ValidationError,
)


@dataclass
class ItemResult:
    label: dict[str, Any]
    tier1: list[ProductCandidate] = field(default_factory=list)
    final: list[ProductCandidate] = field(default_factory=list)
    called_tier2: bool = False
    error: str = ""


async def run_item(label: dict[str, Any]) -> ItemResult:
    capture = IdentifyRequest.model_validate_json(
        capture_path(label["video_id"], label["timestamp"]).read_text()
    )
    state = PipelineState(
        video_id=capture.video_id,
        frame=capture.frames[0],  # captures keep only the sharpest frame
        title=capture.title,
        description=capture.description,
        transcript=capture.transcript,
    )
    result = ItemResult(label)
    async for update in build_graph().astream(state, stream_mode="updates"):
        for node, values in update.items():
            if node == "identify":
                result.tier1 = values["candidates"]
            else:
                result.called_tier2 = True
            result.final = values["candidates"]
    return result


async def run_with_retries(label: dict[str, Any]) -> ItemResult:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await run_item(label)
        except RateLimited as error:
            if attempt == MAX_ATTEMPTS:
                return ItemResult(label, error=str(error))
            print(f"  rate limited, sleeping {error.retry_after_seconds:.0f}s")
            await asyncio.sleep(error.retry_after_seconds)
        except ITEM_ERRORS as error:  # one bad item shouldn't stop the run
            return ItemResult(label, error=f"{type(error).__name__}: {error}")
    raise AssertionError("unreachable")


def runnable_labels(subset: str) -> tuple[list[dict[str, Any]], int, int]:
    """Labeled items with a capture, plus counts of unlabeled and missing captures."""
    labels = read_labels()
    if subset == "dev":
        labels = labels[:DEV_SUBSET_SIZE]
    unlabeled = [item for item in labels if not (item["brand"] and item["model"])]
    labeled = [item for item in labels if item["brand"] and item["model"]]
    ready = [
        item
        for item in labeled
        if capture_path(item["video_id"], item["timestamp"]).exists()
    ]
    return ready, len(unlabeled), len(labeled) - len(ready)


def report(results: list[ItemResult], unlabeled: int, missing: int) -> str:
    settings = get_settings()
    n = len(results)
    tier1 = sum(
        top1_correct(r.label["brand"], r.label["model"], r.tier1) for r in results
    )
    final = sum(
        top1_correct(r.label["brand"], r.label["model"], r.final) for r in results
    )
    tier2_calls = sum(r.called_tier2 for r in results)
    errors = sum(bool(r.error) for r in results)

    def share(count: int) -> str:
        return f"{count}/{n} ({count / n:.0%})" if n else "0/0"

    lines = [
        f"# Identify eval, {date.today().isoformat()}",
        "",
        f"- Prompt version: `{PROMPT_VERSION}`",
        f"- Tier 1 model: `{settings.model_spec_for(Role.IDENTIFY_VISION)}`",
        f"- Tier 2 model: `{settings.model_spec_for(Role.DISAMBIGUATE)}`",
        f"- Tier 2 threshold: {settings.tier2_confidence_threshold}",
        (
            f"- Items run: {n} (skipped: {unlabeled} unlabeled, "
            f"{missing} without a capture; {errors} errors, counted as wrong)"
        ),
        "",
        "| Config | Top-1 correct |",
        "|---|---|",
        f"| Tier 1 only | {share(tier1)} |",
        f"| Tier 1+2 | {share(final)} |",
        "",
        f"Tier 2 called: {share(tier2_calls)}",
        "",
        "## Items",
        "",
        "| Video | t | Label | Tier 1 top | Final top | Tier 2 | Error |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.label['video_id']} | {r.label['timestamp']} "
            f"| {r.label['brand']} {r.label['model']} | {_top(r.tier1)} | {_top(r.final)} "
            f"| {'yes' if r.called_tier2 else 'no'} | {r.error} |"
        )
    return "\n".join(lines) + "\n"


def _top(candidates: list[ProductCandidate]) -> str:
    return f"{candidates[0].brand} {candidates[0].model}" if candidates else "none"


async def main(subset: str) -> None:
    settings = get_settings()
    # Never re-spend quota on an unchanged item; replay stays replay if set.
    if settings.llm_mode == "live":
        settings.llm_mode = "record"
    labels, unlabeled, missing = runnable_labels(subset)
    results = []
    for index, label in enumerate(labels, start=1):
        print(f"[{index}/{len(labels)}] {label['video_id']} @ {label['timestamp']}")
        results.append(await run_with_retries(label))
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{date.today().isoformat()}-identify.md"
    path.write_text(report(results, unlabeled, missing))
    print(f"Report: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", choices=["dev", "full"], default="dev")
    asyncio.run(main(parser.parse_args().subset))
