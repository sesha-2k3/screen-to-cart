"""Typed, env-driven configuration for the Screen to Cart backend.

Values come from environment variables and the repo-root ``.env`` file (edited only
by the user; a missing file is ignored). Source order is the pydantic-settings
default: init kwargs > environment > dotenv > field defaults, merged per field.

No field has a model-name or secret default. Model specs are ``provider:model``
strings set in ``.env`` (see ``.env.example``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

if TYPE_CHECKING:
    from app.llm.factory import Role

# backend/app/config.py -> parents[2] is the repo root.
REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"

LlmMode = Literal["live", "record", "replay"]

# Role value -> Settings field holding that role's model spec.
_ROLE_FIELDS: dict[str, str] = {
    "identify_vision": "identify_vision_model",
    "disambiguate": "disambiguate_model",
    "refine": "refine_model",
    "sponsorship": "sponsorship_model",
}

_OPTIONAL_FIELDS = (
    "database_url",
    "groq_api_key",
    "anthropic_api_key",
    "identify_vision_model",
    "disambiguate_model",
    "refine_model",
    "sponsorship_model",
    "langfuse_public_key",
    "langfuse_secret_key",
    "ebay_client_id",
    "ebay_client_secret",
    "bestbuy_api_key",
    "siglip_model",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = None

    groq_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = (
        None  # optional, for the later provider switch
    )

    identify_vision_model: str | None = None
    disambiguate_model: str | None = None
    refine_model: str | None = None
    sponsorship_model: str | None = None
    llm_mode: LlmMode = "live"
    tier2_confidence_threshold: float = 0.7
    # Groq free-plan tokens per minute; check console.groq.com/settings/limits.
    groq_tpm_limit: int = 8000
    save_eval_captures: bool = False

    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"

    ebay_client_id: SecretStr | None = None
    ebay_client_secret: SecretStr | None = None
    bestbuy_api_key: SecretStr | None = None

    siglip_model: str | None = None

    cors_allowed_origins: Annotated[list[str], NoDecode] = []

    @field_validator(*_OPTIONAL_FIELDS, mode="before")
    @classmethod
    def _empty_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v == "":
            return None
        return v

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _sponsorship_fallback(self) -> Settings:
        if not (self.sponsorship_model and self.sponsorship_model.strip()):
            self.sponsorship_model = self.refine_model
        return self

    def model_spec_for(self, role: Role | str) -> str | None:
        """Return the model spec configured for ``role`` (a Role or its string value)."""
        key = str(getattr(role, "value", role))
        field = _ROLE_FIELDS.get(key)
        if field is None:
            valid = ", ".join(_ROLE_FIELDS)
            raise ValueError(f"Invalid role {role!r}. Valid roles: {valid}")
        return getattr(self, field)


@lru_cache
def get_settings() -> Settings:
    return Settings()
