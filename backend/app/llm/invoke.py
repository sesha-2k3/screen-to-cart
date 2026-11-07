"""One JSON-returning LLM call: rate limit, record/replay, validate, retry once."""

from __future__ import annotations

import groq
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.llm.factory import Role, get_llm
from app.llm.fixtures import fixture_key, read_fixture, write_fixture
from app.llm.rate_limit import RateLimited, bucket_for

# Groq counts every image as 2,048 input tokens regardless of size.
IMAGE_TOKENS = 2048
OUTPUT_TOKENS_ESTIMATE = 1024
# Used when a 429 has no retry-after header.
DEFAULT_RETRY_AFTER_SECONDS = 60.0


class LlmOutputError(Exception):
    """The model returned output that doesn't match the schema, twice."""


class FixtureMissingError(Exception):
    """LLM_MODE=replay and no stored response exists for this request."""


async def invoke_json[T: BaseModel](
    role: Role,
    messages: list[BaseMessage],
    schema: type[T],
    prompt_version: str,
    config: RunnableConfig | None = None,
    settings: Settings | None = None,
) -> T:
    settings = settings or get_settings()
    model_spec = settings.model_spec_for(role) or ""
    key = fixture_key(model_spec, messages)
    if settings.llm_mode != "live":
        stored = read_fixture(key)
        if stored is not None:
            return _validate(stored, schema, role)
        if settings.llm_mode == "replay":
            raise FixtureMissingError(f"No fixture {key} for role {role.value}")

    model = get_llm(role, settings)
    bucket = bucket_for(model_spec, settings.groq_tpm_limit)
    last_error: ValidationError | None = None
    for _ in range(2):
        await bucket.acquire(_estimate_tokens(messages))
        try:
            response = await model.ainvoke(messages, config)
        except groq.RateLimitError as error:
            raise RateLimited(_retry_after(error)) from error
        content = str(response.text)
        try:
            result = schema.model_validate_json(content)
        except ValidationError as error:
            last_error = error
            continue
        if settings.llm_mode == "record":
            write_fixture(key, role.value, model_spec, prompt_version, content)
        return result
    raise LlmOutputError(
        f"{role.value} returned invalid output twice: {last_error}"
    ) from last_error


def _validate[T: BaseModel](content: str, schema: type[T], role: Role) -> T:
    try:
        return schema.model_validate_json(content)
    except ValidationError as error:
        raise LlmOutputError(
            f"Stored {role.value} output is invalid: {error}"
        ) from error


def _estimate_tokens(messages: list[BaseMessage]) -> int:
    images, characters = 0, 0
    for message in messages:
        parts = (
            message.content if isinstance(message.content, list) else [message.content]
        )
        for part in parts:
            if isinstance(part, str):
                characters += len(part)
            elif part.get("type") == "image_url":
                images += 1
            else:
                characters += len(str(part.get("text", "")))
    return images * IMAGE_TOKENS + characters // 4 + OUTPUT_TOKENS_ESTIMATE


def _retry_after(error: groq.RateLimitError) -> float:
    header = error.response.headers.get("retry-after")
    try:
        return float(header) if header else DEFAULT_RETRY_AFTER_SECONDS
    except ValueError:
        return DEFAULT_RETRY_AFTER_SECONDS
