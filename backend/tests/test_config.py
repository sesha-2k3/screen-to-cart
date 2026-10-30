"""Tests for ``app.config.Settings``."""

from __future__ import annotations

import random
import string
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

_SEED = 20240605
_CASES = 100
_PROVIDERS = ("groq", "anthropic", "openai", "local")
_NAME_CHARS = string.ascii_lowercase + string.digits + "-._/"
_WHITESPACE = " \t\n\r\f\v"


def _random_spec(rng: random.Random) -> str:
    """A random ``provider:model`` spec with no surrounding whitespace."""
    provider = rng.choice(_PROVIDERS)
    first = rng.choice(string.ascii_lowercase)
    rest = "".join(rng.choices(_NAME_CHARS, k=rng.randint(0, 24)))
    return f"{provider}:{first}{rest}"


def _random_sponsorship(rng: random.Random) -> str | None:
    """``None`` (unset), ``""``, whitespace-only, or a random spec."""
    kind = rng.randrange(4)
    if kind == 0:
        return None
    if kind == 1:
        return ""
    if kind == 2:
        return "".join(rng.choices(_WHITESPACE, k=rng.randint(1, 6)))
    return _random_spec(rng)


def _sponsorship_cases() -> list[tuple[str, str | None]]:
    rng = random.Random(_SEED)
    return [(_random_spec(rng), _random_sponsorship(rng)) for _ in range(_CASES)]


# Feature: phase-0-setup, Property 5: Sponsorship falls back to the refine model
# **Validates: Requirements 5.2, 5.3, 13.3**
@pytest.mark.parametrize(("refine", "sponsorship"), _sponsorship_cases())
def test_sponsorship_falls_back_to_refine_model(
    monkeypatch: pytest.MonkeyPatch, refine: str, sponsorship: str | None
) -> None:
    monkeypatch.setenv("REFINE_MODEL", refine)
    if sponsorship is None:
        monkeypatch.delenv("SPONSORSHIP_MODEL", raising=False)
    else:
        monkeypatch.setenv("SPONSORSHIP_MODEL", sponsorship)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    if sponsorship is None or not sponsorship.strip():
        expected = refine
    else:
        expected = sponsorship
    assert settings.refine_model == refine
    assert settings.sponsorship_model == expected
    assert settings.model_spec_for("sponsorship") == expected


_VALID_MODES = ("live", "record", "replay")
_NEAR_MISS_MODES = ("LIVE", " live", "", "live ", "Replay", "recorded")
_MODE_CHARS = string.ascii_letters + string.digits + string.punctuation + " "


def _random_mode(rng: random.Random) -> str:
    """A valid mode, a near miss, or a random printable string that is never valid."""
    kind = rng.randrange(3)
    if kind == 0:
        return rng.choice(_VALID_MODES)
    if kind == 1:
        return rng.choice(_NEAR_MISS_MODES)
    while True:
        candidate = "".join(rng.choices(_MODE_CHARS, k=rng.randint(1, 12)))
        if candidate not in _VALID_MODES:
            return candidate


def _mode_cases() -> list[str]:
    rng = random.Random(_SEED + 6)
    # Always cover every valid value and every named near miss.
    cases = [*_VALID_MODES, *_NEAR_MISS_MODES]
    cases += [_random_mode(rng) for _ in range(_CASES - len(cases))]
    return cases


# Feature: phase-0-setup, Property 6: LLM_MODE accepts exactly three values
# **Validates: Requirements 5.4, 5.5, 13.3**
@pytest.mark.parametrize("mode", _mode_cases())
def test_settings_llm_mode_accepts_exactly_three_values(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("LLM_MODE", mode)

    if mode in _VALID_MODES:
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.llm_mode == mode
        return

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    locations = [err["loc"] for err in exc_info.value.errors()]
    assert ("llm_mode",) in locations


_EXTENSION_ID_CHARS = "abcdefghijklmnop"  # Chrome extension IDs use a-p only
_SPACES = " \t"


def _random_origin(rng: random.Random) -> str:
    """A ``chrome-extension://<32 a-p>`` or ``http://localhost:<port>`` origin."""
    if rng.randrange(2) == 0:
        return "chrome-extension://" + "".join(rng.choices(_EXTENSION_ID_CHARS, k=32))
    return f"http://localhost:{rng.randint(1, 65535)}"


def _pad(rng: random.Random) -> str:
    """Optional whitespace placed around commas and at the ends."""
    return "".join(rng.choices(_SPACES, k=rng.randint(0, 3)))


def _cors_cases() -> list[tuple[str, str, list[str]]]:
    """``(source, raw value, expected list)``; source is ``env`` or ``init``."""
    rng = random.Random(_SEED + 8)
    cases: list[tuple[str, str, list[str]]] = []
    for i in range(_CASES):
        source = "env" if i % 2 == 0 else "init"
        if i % 10 == 9:
            # Empty and whitespace-only values give an empty list.
            raw = "".join(rng.choices(_SPACES, k=rng.randint(0, 5)))
            cases.append((source, raw, []))
            continue
        origins = [_random_origin(rng) for _ in range(rng.randint(0, 5))]
        body = origins[0] if origins else ""
        for origin in origins[1:]:
            body += f"{_pad(rng)},{_pad(rng)}{origin}"
        raw = _pad(rng) + body + _pad(rng)
        cases.append((source, raw, origins))
    return cases


# Feature: phase-0-setup, Property 8: CORS origin list parse round trip
# **Validates: Requirements 8.5**
@pytest.mark.parametrize(("source", "raw", "expected"), _cors_cases())
def test_settings_cors_origins_round_trip(
    monkeypatch: pytest.MonkeyPatch, source: str, raw: str, expected: list[str]
) -> None:
    if source == "env":
        # The env path is where NoDecode matters: the raw string is not JSON-decoded.
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", raw)
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
    else:
        settings = Settings(_env_file=None, cors_allowed_origins=raw)  # type: ignore[call-arg]

    assert settings.cors_allowed_origins == expected


# **Validates: Requirements 5.8, 5.9, 13.7**
def test_settings_env_overrides_dotenv_and_sources_merge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "REFINE_MODEL=groq:from-file\nDISAMBIGUATE_MODEL=groq:file-only\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("REFINE_MODEL", "groq:from-env")
    monkeypatch.setenv("IDENTIFY_VISION_MODEL", "groq:env-only")

    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]

    assert settings.refine_model == "groq:from-env"
    assert settings.identify_vision_model == "groq:env-only"
    assert settings.disambiguate_model == "groq:file-only"
