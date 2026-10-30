"""Tests for ``app.llm.factory``: model spec parsing and ``get_llm``."""

from __future__ import annotations

import random
import string
import sys
from collections.abc import Callable

import pytest

from app.config import Settings
from app.llm.factory import (
    LlmConfigError,
    ProviderNotInstalledError,
    Role,
    get_llm,
    parse_model_spec,
)

_ROLES: tuple[Role, ...] = tuple(Role)
_PROPERTY_CASES = 100


# ---------------------------------------------------------------------------
# Generators (fixed seed, no hypothesis)
# ---------------------------------------------------------------------------

_PROVIDER_ALPHABET = string.ascii_lowercase + string.digits + "_-"
# Printable, non-whitespace characters; always includes "/", ":", ".", "-".
_MODEL_ALPHABET = "".join(c for c in string.printable if not c.isspace())


def _gen_provider(rng: random.Random) -> str:
    return "".join(rng.choices(_PROVIDER_ALPHABET, k=rng.randint(1, 12)))


def _gen_model(rng: random.Random) -> str:
    model = "".join(rng.choices(_MODEL_ALPHABET, k=rng.randint(1, 40)))
    # Make sure a good share of cases put a ":" or "/" inside the model.
    if rng.random() < 0.5:
        cut = rng.randint(0, len(model))
        model = model[:cut] + rng.choice(":/") + model[cut:]
    return model


_FIXED_MALFORMED_SPECS: tuple[str, ...] = (":x", "x:", "  :  ")
_WHITESPACE = " \t"
# Non-whitespace characters without the separator, for specs with no ":".
_NO_COLON_ALPHABET = _MODEL_ALPHABET.replace(":", "")


def _gen_whitespace(rng: random.Random) -> str:
    return "".join(rng.choices(_WHITESPACE, k=rng.randint(0, 4)))


def _gen_malformed_spec(rng: random.Random) -> str:
    kind = rng.choice(("no_colon", "empty_provider", "empty_model", "both_empty"))
    if kind == "no_colon":
        body = "".join(rng.choices(_NO_COLON_ALPHABET, k=rng.randint(1, 40)))
        return _gen_whitespace(rng) + body + _gen_whitespace(rng)
    provider = "" if kind in ("empty_provider", "both_empty") else _gen_provider(rng)
    # Whitespace-only sides are stripped to empty; the other side has no ":".
    model = (
        ""
        if kind in ("empty_model", "both_empty")
        else "".join(rng.choices(_NO_COLON_ALPHABET, k=rng.randint(1, 20)))
    )
    return (
        _gen_whitespace(rng)
        + provider
        + _gen_whitespace(rng)
        + ":"
        + _gen_whitespace(rng)
        + model
        + _gen_whitespace(rng)
    )


def _malformed_cases() -> list[tuple[str, Role]]:
    cases = [(spec, role) for spec in _FIXED_MALFORMED_SPECS for role in _ROLES]
    rng = random.Random(20240602)
    i = 0
    while len(cases) < _PROPERTY_CASES:
        cases.append((_gen_malformed_spec(rng), _ROLES[i % len(_ROLES)]))
        i += 1
    return cases


def _round_trip_cases() -> list[tuple[str, str, Role]]:
    rng = random.Random(20240601)
    return [
        (_gen_provider(rng), _gen_model(rng), _ROLES[i % len(_ROLES)])
        for i in range(_PROPERTY_CASES)
    ]


# ---------------------------------------------------------------------------
# parse_model_spec
# ---------------------------------------------------------------------------


# Feature: phase-0-setup, Property 1: Model spec parse round trip
# **Validates: Requirements 6.2**
@pytest.mark.parametrize(("provider", "model", "role"), _round_trip_cases())
def test_parse_model_spec_round_trip(provider: str, model: str, role: Role) -> None:
    assert parse_model_spec(f"{provider}:{model}", role) == (provider, model)


# Feature: phase-0-setup, Property 2: Malformed model specs are rejected
# **Validates: Requirements 6.7**
@pytest.mark.parametrize(("spec", "role"), _malformed_cases())
def test_parse_model_spec_rejects_malformed(spec: str, role: Role) -> None:
    with pytest.raises(LlmConfigError) as exc_info:
        parse_model_spec(spec, role)
    message = str(exc_info.value)
    assert role.value in message
    assert repr(spec) in message


# Feature: phase-0-setup, Property 2: Malformed model specs are rejected
# **Validates: Requirements 6.7**
@pytest.mark.parametrize(("spec", "role"), _malformed_cases())
def test_get_llm_rejects_malformed_spec(
    spec: str, role: Role, make_settings: Callable[..., Settings]
) -> None:
    settings = make_settings(groq_api_key="dummy-key", **{f"{role.value}_model": spec})
    with pytest.raises(LlmConfigError) as exc_info:
        get_llm(role, settings)
    message = str(exc_info.value)
    assert role.value in message
    assert repr(spec) in message


# ---------------------------------------------------------------------------
# get_llm: unknown roles and providers
# ---------------------------------------------------------------------------

_ROLE_VALUES = frozenset(r.value for r in Role)
_SUPPORTED_PROVIDERS = ("groq", "anthropic")
# Role coercion is an exact Role(value) lookup, so any other string is invalid,
# including case or whitespace variants of a real role.
_FIXED_NON_ROLES: tuple[str, ...] = (
    "",
    " ",
    "REFINE",
    " refine",
    "identify",
    "identify-vision",
    "verify",
)
# Provider lookup is exact after strip(), so uppercase variants are unsupported.
_FIXED_UNSUPPORTED_PROVIDERS: tuple[str, ...] = ("GROQ", "Anthropic", "openai")
_UNKNOWN_PROVIDER_ALPHABET = string.ascii_letters + string.digits + "_-."


def _non_role_cases() -> list[str]:
    cases = list(_FIXED_NON_ROLES)
    rng = random.Random(20240603)
    while len(cases) < _PROPERTY_CASES:
        candidate = "".join(rng.choices(string.printable, k=rng.randint(0, 20)))
        if rng.random() < 0.3:
            # Near misses: a real role with a random suffix.
            candidate = rng.choice(sorted(_ROLE_VALUES)) + candidate
        if candidate not in _ROLE_VALUES:
            cases.append(candidate)
    return cases


def _unknown_provider_cases() -> list[tuple[str, Role]]:
    cases = [(p, role) for p in _FIXED_UNSUPPORTED_PROVIDERS for role in _ROLES]
    rng = random.Random(20240604)
    i = 0
    while len(cases) < _PROPERTY_CASES:
        provider = "".join(
            rng.choices(_UNKNOWN_PROVIDER_ALPHABET, k=rng.randint(1, 12))
        )
        if provider.strip() not in _SUPPORTED_PROVIDERS:
            cases.append((provider, _ROLES[i % len(_ROLES)]))
            i += 1
    return cases


# Feature: phase-0-setup, Property 3: Unknown roles and providers produce descriptive errors
# **Validates: Requirements 6.5**
@pytest.mark.parametrize("bad_role", _non_role_cases())
def test_get_llm_rejects_unknown_role(
    bad_role: str, make_settings: Callable[..., Settings]
) -> None:
    settings = make_settings(groq_api_key="dummy-key")
    with pytest.raises(LlmConfigError) as exc_info:
        get_llm(bad_role, settings)
    message = str(exc_info.value)
    assert repr(bad_role) in message
    for role in _ROLES:
        assert role.value in message


# Feature: phase-0-setup, Property 3: Unknown roles and providers produce descriptive errors
# **Validates: Requirements 6.6**
@pytest.mark.parametrize(("provider", "role"), _unknown_provider_cases())
def test_get_llm_rejects_unknown_provider(
    provider: str, role: Role, make_settings: Callable[..., Settings]
) -> None:
    settings = make_settings(
        groq_api_key="dummy-key", **{f"{role.value}_model": f"{provider}:some-model"}
    )
    with pytest.raises(LlmConfigError) as exc_info:
        get_llm(role, settings)
    message = str(exc_info.value)
    assert repr(provider.strip()) in message
    assert role.value in message
    for supported in _SUPPORTED_PROVIDERS:
        assert supported in message


# ---------------------------------------------------------------------------
# get_llm: Groq construction
# ---------------------------------------------------------------------------

_DUMMY_KEY_ALPHABET = string.ascii_letters + string.digits + "_-"


def _groq_cases() -> list[tuple[Role, str, str]]:
    rng = random.Random(20240605)
    return [
        (
            _ROLES[i % len(_ROLES)],
            # _gen_model yields non-whitespace characters, so it survives strip().
            _gen_model(rng),
            "dummy-" + "".join(rng.choices(_DUMMY_KEY_ALPHABET, k=rng.randint(1, 24))),
        )
        for i in range(_PROPERTY_CASES)
    ]


# Feature: phase-0-setup, Property 4: Groq specs build an offline ChatGroq for the configured role
# **Validates: Requirements 6.1, 6.3, 6.9, 6.10**
@pytest.mark.parametrize(("role", "model", "api_key"), _groq_cases())
def test_get_llm_builds_groq_offline(
    role: Role, model: str, api_key: str, make_settings: Callable[..., Settings]
) -> None:
    from langchain_groq import ChatGroq

    settings = make_settings(
        groq_api_key=api_key, **{f"{role.value}_model": f"groq:{model}"}
    )
    # The autouse socket guard fails the test if construction opens a connection.
    result = get_llm(role, settings)
    assert type(result) is ChatGroq
    assert result.model_name == model
    assert result.groq_api_key is not None
    assert result.groq_api_key.get_secret_value() == api_key


# ---------------------------------------------------------------------------
# get_llm: error cases (unit tests)
# Requirements 6.4, 6.11, 13.4, 13.8
# ---------------------------------------------------------------------------


def test_get_llm_anthropic_not_installed_raises_provider_error(
    monkeypatch: pytest.MonkeyPatch, make_settings: Callable[..., Settings]
) -> None:
    # A None entry in sys.modules makes `import langchain_anthropic` raise ImportError.
    monkeypatch.setitem(sys.modules, "langchain_anthropic", None)
    settings = make_settings(refine_model="anthropic:some-model")

    with pytest.raises(ProviderNotInstalledError) as exc_info:
        get_llm(Role.REFINE, settings)
    assert "uv add langchain-anthropic" in str(exc_info.value)

    # Callers that only catch the base config error also catch this one.
    with pytest.raises(LlmConfigError):
        get_llm(Role.REFINE, settings)


def test_provider_not_installed_error_is_documented_config_error() -> None:
    assert issubclass(ProviderNotInstalledError, LlmConfigError)
    assert ProviderNotInstalledError.__doc__
    assert ProviderNotInstalledError.__doc__.strip()


def test_get_llm_groq_without_api_key_names_env_var(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(refine_model="groq:some-model")
    with pytest.raises(LlmConfigError) as exc_info:
        get_llm(Role.REFINE, settings)
    assert "GROQ_API_KEY" in str(exc_info.value)


def test_get_llm_unset_role_spec_names_role_and_env_var(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(groq_api_key="dummy-key")
    with pytest.raises(LlmConfigError) as exc_info:
        get_llm(Role.REFINE, settings)
    message = str(exc_info.value)
    assert "refine" in message
    assert "REFINE_MODEL" in message
