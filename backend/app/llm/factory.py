"""LLM provider factory.

Every pipeline node gets its chat model from ``get_llm(role)``. The role's model
spec (``provider:model``) comes from Settings, so switching models or providers is
a configuration change. This module holds no model names.

``LLM_MODE`` (record/replay) is handled by ``app.llm.invoke``, not here.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

import httpx
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings, get_settings
from app.llm.rate_limit import bucket_for


class Role(StrEnum):
    IDENTIFY_VISION = "identify_vision"
    DISAMBIGUATE = "disambiguate"
    REFINE = "refine"
    SPONSORSHIP = "sponsorship"


# Env var that configures each role's model spec, used in error messages.
_ROLE_ENV_VARS: dict[Role, str] = {
    Role.IDENTIFY_VISION: "IDENTIFY_VISION_MODEL",
    Role.DISAMBIGUATE: "DISAMBIGUATE_MODEL",
    Role.REFINE: "REFINE_MODEL",
    Role.SPONSORSHIP: "SPONSORSHIP_MODEL",
}


class LlmConfigError(ValueError):
    """Bad role, malformed or missing model spec, or unsupported provider."""


class ProviderNotInstalledError(LlmConfigError):
    """The configured provider's LangChain package is not installed.

    Raised instead of ``ImportError``. The message names the package and the
    ``uv add`` command that installs it. Catching ``LlmConfigError`` also catches
    this error.
    """


def _coerce_role(role: Role | str) -> Role:
    try:
        return Role(role)
    except ValueError:
        valid = ", ".join(r.value for r in Role)
        raise LlmConfigError(f"Invalid role {role!r}. Valid roles: {valid}") from None


def parse_model_spec(spec: str, role: Role | str) -> tuple[str, str]:
    """Split ``spec`` on the first ``:`` into ``(provider, model)``.

    Raises ``LlmConfigError`` naming the role and the spec when the separator,
    the provider or the model is missing.
    """
    provider, sep, model = spec.partition(":")
    provider, model = provider.strip(), model.strip()
    if not sep or not provider or not model:
        raise LlmConfigError(
            f"Malformed model spec {spec!r} for role {role!s}: "
            "expected 'provider:model'"
        )
    return provider, model


def _build_groq(model: str, role: Role, settings: Settings) -> BaseChatModel:
    from langchain_groq import ChatGroq

    if settings.groq_api_key is None:
        raise LlmConfigError(f"GROQ_API_KEY is not set (role={role.value})")
    # Construction sends no request; the instance is returned as is.
    return ChatGroq(
        model=model,
        api_key=settings.groq_api_key,
        http_async_client=_groq_http_client(f"groq:{model}", settings),
        # The SDK would retry 429s for up to a minute while the panel looks frozen.
        max_retries=0,
        # Every role returns JSON; the prompt carries the shape, so this stays portable.
        model_kwargs={"response_format": {"type": "json_object"}},
    )


_http_clients: dict[str, httpx.AsyncClient] = {}


def _groq_http_client(model_spec: str, settings: Settings) -> httpx.AsyncClient:
    # One client per model, shared across requests. ChatGroq doesn't expose response
    # headers, so the rate limiter reads them through this client's response hook.
    if model_spec not in _http_clients:
        bucket = bucket_for(model_spec, settings.groq_tpm_limit)
        _http_clients[model_spec] = httpx.AsyncClient(
            event_hooks={"response": [bucket.observe]}
        )
    return _http_clients[model_spec]


def _build_anthropic(model: str, role: Role, settings: Settings) -> BaseChatModel:
    try:
        # Optional provider package; not installed in Phase 0.
        import langchain_anthropic  # type: ignore[import-not-found, unused-ignore]
    except ImportError:
        raise ProviderNotInstalledError(
            f"Provider 'anthropic' (role={role.value}) needs langchain-anthropic. "
            "Run: uv add langchain-anthropic"
        ) from None
    chat_cls: Callable[..., BaseChatModel] = langchain_anthropic.ChatAnthropic
    return chat_cls(model=model, api_key=settings.anthropic_api_key)


_BUILDERS: dict[str, Callable[[str, Role, Settings], BaseChatModel]] = {
    "groq": _build_groq,
    "anthropic": _build_anthropic,
}


def get_llm(role: Role | str, settings: Settings | None = None) -> BaseChatModel:
    """Return the chat model configured for ``role``."""
    settings = settings or get_settings()
    resolved = _coerce_role(role)
    spec = settings.model_spec_for(resolved)
    if spec is None or not spec.strip():
        raise LlmConfigError(
            f"No model spec configured for role {resolved.value}: "
            f"set {_ROLE_ENV_VARS[resolved]} to 'provider:model'"
        )
    provider, model = parse_model_spec(spec, resolved)
    builder = _BUILDERS.get(provider)
    if builder is None:
        supported = ", ".join(_BUILDERS)
        raise LlmConfigError(
            f"Unsupported provider {provider!r} for role {resolved.value}. "
            f"Supported providers: {supported}"
        )
    return builder(model, resolved, settings)
