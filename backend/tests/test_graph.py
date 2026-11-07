from typing import Any

import pytest
from langchain_core.messages import BaseMessage

from app.graph.build import needs_tier2
from app.graph.confidence import rank
from app.graph.nodes import disambiguate as disambiguate_module
from app.graph.nodes import identify as identify_module
from app.graph.nodes.disambiguate import disambiguate
from app.graph.nodes.identify import identify
from app.graph.state import PipelineState
from app.llm.factory import Role
from app.schemas import Candidates, Evidence, ProductCandidate, TranscriptSegment


def candidate(model: str, confidence: float) -> ProductCandidate:
    return ProductCandidate(
        brand="Sony",
        model=model,
        category="headphones",
        confidence=confidence,
        evidence=[Evidence(source="visual", detail="SONY on the headband")],
        search_queries=[f"Sony {model}"],
        visual_notes="black over-ear headphones, SONY on the headband",
    )


def state(**extra: Any) -> PipelineState:
    return PipelineState(
        video_id="abc123",
        frame="FRAME",
        title="Best headphones of 2026",
        description="Sony WH-1000XM5: https://example.com/xm5",
        transcript=[TranscriptSegment(start=40, duration=2, text="these Sonys")],
        **extra,
    )


class FakeInvoke:
    """Stands in for invoke_json and records what each node sent."""

    def __init__(self, result: Candidates) -> None:
        self.result = result
        self.calls: list[tuple[Role, list[BaseMessage]]] = []

    async def __call__(
        self, role: Role, messages: list[BaseMessage], *args: Any, **kwargs: Any
    ) -> Candidates:
        self.calls.append((role, messages))
        return self.result


def image_count(messages: list[BaseMessage]) -> int:
    return sum(
        1
        for message in messages
        if isinstance(message.content, list)
        for part in message.content
        if isinstance(part, dict) and part.get("type") == "image_url"
    )


async def test_identify_sends_one_image_and_returns_tier1_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeInvoke(Candidates(candidates=[candidate("WH-1000XM5", 0.9)]))
    monkeypatch.setattr(identify_module, "invoke_json", fake)
    update = await identify(state(), {})
    [(role, messages)] = fake.calls
    assert role is Role.IDENTIFY_VISION
    assert image_count(messages) == 1
    assert update["tier"] == 1
    assert update["candidates"][0].model == "WH-1000XM5"


async def test_disambiguate_sends_no_image_and_returns_tier2_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeInvoke(Candidates(candidates=[candidate("WH-1000XM5", 0.85)]))
    monkeypatch.setattr(disambiguate_module, "invoke_json", fake)
    tier1 = [candidate("WH-1000XM4", 0.5), candidate("WH-1000XM5", 0.4)]
    update = await disambiguate(state(candidates=tier1, tier=1), {})
    [(role, messages)] = fake.calls
    assert role is Role.DISAMBIGUATE
    assert image_count(messages) == 0
    assert "WH-1000XM4" in str(messages[0].content)
    assert update == {"candidates": fake.result.candidates, "tier": 2}


def test_needs_tier2_skips_a_clear_winner_seen_in_the_frame() -> None:
    candidates = [candidate("WH-1000XM5", 0.75), candidate("WH-1000XM4", 0.2)]
    assert not needs_tier2(candidates, threshold=0.7, margin=0.3)


def test_needs_tier2_runs_on_low_confidence() -> None:
    assert needs_tier2([candidate("WH-1000XM5", 0.6)], threshold=0.7, margin=0.3)


def test_needs_tier2_runs_on_a_close_runner_up() -> None:
    candidates = [candidate("WH-1000XM5", 0.5), candidate("WH-1000XM4", 0.4)]
    assert needs_tier2(candidates, threshold=0.3, margin=0.3)


def test_needs_tier2_runs_when_the_top_guess_has_no_visual_evidence() -> None:
    text_only = candidate("WH-1000XM5", 0.9).model_copy(
        update={"evidence": [Evidence(source="transcript", detail="mine are the XM5")]}
    )
    assert needs_tier2([text_only], threshold=0.7, margin=0.3)


def test_rank_sorts_and_scales_confidences_to_at_most_one() -> None:
    ranked = rank([candidate("WH-1000XM4", 0.9), candidate("WH-1000XM5", 0.95)])
    assert [c.model for c in ranked] == ["WH-1000XM5", "WH-1000XM4"]
    assert sum(c.confidence for c in ranked) == pytest.approx(1)
    assert ranked[0].confidence == pytest.approx(0.95 / 1.85)
