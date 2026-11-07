from collections.abc import Callable
from pathlib import Path

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from app.config import Settings
from app.llm import invoke
from app.llm.factory import Role
from app.llm.invoke import FixtureMissingError, LlmOutputError, invoke_json
from app.schemas import Candidates

VALID = '{"candidates": []}'
IMAGE = "data:image/jpeg;base64,SECRETFRAME"
MESSAGES = [
    HumanMessage(
        content=[
            {"type": "text", "text": "What is this?"},
            {"type": "image_url", "image_url": {"url": IMAGE}},
        ]
    )
]


@pytest.fixture(autouse=True)
def _fixtures_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.llm.fixtures.FIXTURES_DIR", tmp_path)


def _fake_llm(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> list[int]:
    """Patch get_llm with a fake model; the returned list counts get_llm calls."""
    calls: list[int] = []

    def fake_get_llm(role: Role, settings: Settings) -> BaseChatModel:
        calls.append(1)
        return FakeListChatModel(responses=responses)

    monkeypatch.setattr(invoke, "get_llm", fake_get_llm)
    return calls


def _settings(make_settings: Callable[..., Settings], mode: str) -> Settings:
    return make_settings(identify_vision_model="groq:test-vision", llm_mode=mode)


async def _identify(settings: Settings) -> Candidates:
    return await invoke_json(
        Role.IDENTIFY_VISION, MESSAGES, Candidates, "test-v1", settings=settings
    )


async def test_invoke_json_retries_once_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch, make_settings: Callable[..., Settings]
) -> None:
    _fake_llm(monkeypatch, ["not json", VALID])
    result = await _identify(_settings(make_settings, "live"))
    assert result.candidates == []


async def test_invoke_json_raises_after_two_invalid_outputs(
    monkeypatch: pytest.MonkeyPatch, make_settings: Callable[..., Settings]
) -> None:
    _fake_llm(monkeypatch, ["not json", '{"wrong": 1}', VALID])
    with pytest.raises(LlmOutputError):
        await _identify(_settings(make_settings, "live"))


async def test_invoke_json_record_calls_the_model_once_and_stores_no_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_settings: Callable[..., Settings],
) -> None:
    calls = _fake_llm(monkeypatch, [VALID])
    settings = _settings(make_settings, "record")
    await _identify(settings)
    await _identify(settings)
    assert len(calls) == 1
    [stored] = tmp_path.iterdir()
    assert "SECRETFRAME" not in stored.read_text()


async def test_invoke_json_replay_raises_on_a_missing_fixture(
    monkeypatch: pytest.MonkeyPatch, make_settings: Callable[..., Settings]
) -> None:
    calls = _fake_llm(monkeypatch, [VALID])
    with pytest.raises(FixtureMissingError):
        await _identify(_settings(make_settings, "replay"))
    assert calls == []
