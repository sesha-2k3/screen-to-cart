# Design Document: Phase 0 Setup

## Overview

Phase 0 builds the skeleton the later phases plug into. It produces:

- a uv-managed Python 3.12 FastAPI backend (`backend/`) with typed settings, an LLM provider factory, Alembic migrations that enable pgvector, a `/health` endpoint and Langfuse tracing;
- a Docker image and a Compose stack (`pgvector/pgvector:pg16` + backend);
- a WXT + React + TypeScript side panel extension (`extension/`) that calls `/health` through a typed client generated from the backend's OpenAPI schema.

The design follows sections 4 and 5 of `docs/screen-to-cart-build-plan.md` and the workspace steering (tech, structure, product). Scope stays at Phase 0: the rate limiter, record/replay behaviour (`LLM_MODE` is only validated, not acted on), LangGraph nodes, retailers, `/lookup` and `/identify` are not built here.

Phase 0 is done when `docker compose up` brings up the database and the API, the side panel shows `backend OK`, and opening the side panel produces a Langfuse trace named `health` tagged `groq-free`.

### Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Model names | Only in `.env.example` and the user's `.env`; Settings fields have no model defaults | Tech rule: never hard-code model names (Req 6.8) |
| Unset model spec | Settings field is `str \| None`; `get_llm` raises a clear error when its role's spec is empty | `/health`, migrations and tests boot without LLM config |
| CORS | New setting `CORS_ALLOWED_ORIGINS`, comma-separated exact origins, default empty | Unpacked extension IDs differ per machine; empty default denies cross-origin until the user sets it |
| Extension backend URL | New build-time var `WXT_BACKEND_URL` in `extension/.env.example`, fallback `http://localhost:8000` | WXT/Vite exposes only `WXT_`/`VITE_`-prefixed vars to client code; the fallback is not a secret |
| Compose DB host | `env_file: .env` by reference plus an `environment:` override of `DATABASE_URL` pointing at host `db` | Compose's `environment:` takes precedence over `env_file:`; nothing reads or copies `.env` |
| Migrations at startup | Backend container runs `alembic upgrade head` before `uvicorn` | `docker compose up` alone gives a migrated DB (Req 3.5, 14.1) |
| Langfuse when unconfigured | Client created with `tracing_enabled=False` when either key is missing | `/health` must return 200 without credentials (Req 9.8) |
| Tracing setup errors | No special handling | The SDK already logs and drops bad values instead of raising; extra error paths are not worth the code (Req 9.10 removed) |
| Tests | Example-based tests for remaining work | Tasks 3–4 used seeded 100-case parametrized tests; those stay, but new tests use a few clear examples (see `engineering.md` steering) |

### Langfuse SDK API (verified)

The current Langfuse Python SDK exposes, at the top level, `get_client`, `observe`, `propagate_attributes` and the `Langfuse` class, and the LangChain handler at `langfuse.langchain.CallbackHandler`. `propagate_attributes` is a module-level context manager taking keyword arguments including `trace_name`, `session_id` and `tags`, and it applies them to the active span and every span created inside it ([Langfuse Python reference](https://python.reference.langfuse.com/langfuse)). It must be entered before or immediately inside the root span. Newer SDK majors (v4/v5) keep these names. The implementation uses only these names, so whichever version `uv lock` resolves works; the implementer should check the `Langfuse(...)` constructor keyword for the base URL (`base_url`, with `host` as the older alias) against the installed version.

## Architecture

```mermaid
flowchart LR
  subgraph Chrome
    SP[Side panel React app] --> AC[lib/api.ts<br/>openapi-fetch client]
  end
  AC -- "GET /health (CORS)" --> API
  subgraph Compose["docker compose (name: screen-to-cart)"]
    API[backend service<br/>FastAPI + uvicorn] -- asyncpg --> DB[(db service<br/>pgvector/pgvector:pg16<br/>screen_to_cart)]
  end
  API -- "OTLP spans (batched)" --> LF[Langfuse Cloud]
  ENV[.env<br/>user-edited] -. "env_file (by reference)" .-> API
  CFG[app/config.py Settings] --> API
  CFG --> LLM[app/llm get_llm role]
  CFG --> OBS[app/observability.py]
  CFG --> ALB[app/db Alembic env.py]
```

Request flow for the Phase 0 health check:

```mermaid
sequenceDiagram
  participant SP as Side panel
  participant API as FastAPI /health
  participant OBS as observability
  participant LF as Langfuse
  SP->>SP: status = "checking"
  SP->>API: GET /health (Origin: chrome-extension://<id>)
  API->>OBS: trace_attributes("health", tags=["groq-free"])
  OBS->>API: observe()-wrapped health_check()
  API-->>SP: 200 {"status":"ok"} + CORS headers
  OBS--)LF: span exported in background (no-op if disabled)
  SP->>SP: status = "backend OK"
```

## Components and Interfaces

### Repository layout produced by Phase 0

```
screen-to-cart/
├── .env.example                 # committed, no secret values
├── README.md                    # "Setup" section = Setup_Guide (variables table)
├── .gitignore                   # already exists; must ignore .env, extension/.env*, .venv, node_modules, .output
├── docker-compose.yml
├── backend/
│   ├── .python-version          # 3.12
│   ├── .dockerignore            # excludes .venv, .env, tests caches
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic.ini              # script_location = app/db/migrations
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── observability.py
│   │   ├── schemas.py
│   │   ├── llm/
│   │   │   ├── __init__.py      # re-exports get_llm, Role, errors
│   │   │   └── factory.py
│   │   └── db/
│   │       ├── __init__.py
│   │       └── migrations/
│   │           ├── env.py
│   │           ├── script.py.mako
│   │           └── versions/0001_enable_pgvector.py
│   └── tests/
│       ├── conftest.py
│       ├── test_config.py
│       ├── test_llm_factory.py
│       ├── test_health.py
│       ├── test_observability.py
│       └── test_repo_hygiene.py
└── extension/
    ├── .env.example             # WXT_BACKEND_URL=
    ├── package.json             # name: screen-to-cart-extension
    ├── pnpm-lock.yaml
    ├── wxt.config.ts
    ├── lib/api.ts
    ├── lib/api-types.ts         # generated, never edited
    └── entrypoints/
        ├── background.ts        # opens side panel on toolbar click
        └── sidepanel/
            ├── index.html
            ├── main.tsx
            ├── App.tsx
            ├── HealthStatus.tsx
            └── healthStatus.ts  # pure state mapping
```

The template's default `popup` and `content` entrypoints are removed; `content.ts` arrives in Phase 1.

### Backend project setup (Req 1)

Commands, run in this order from the repo root (section 5):

```bash
uv init backend --app --python 3.12 --name screen-to-cart-backend
cd backend
# 1. add the pytorch-cpu index + torch source to pyproject.toml (below) BEFORE adding torch
uv add fastapi "uvicorn[standard]" sse-starlette pydantic pydantic-settings
uv add langgraph langchain-core langchain-groq
uv add langfuse
uv add httpx
uv add "sqlalchemy[asyncio]" asyncpg alembic pgvector
uv add opencv-python-headless pillow numpy torch transformers sentencepiece
uv add rapidfuzz
uv add --dev pytest pytest-asyncio respx ruff mypy
uv add --group eval pandas matplotlib
```

`uv add` writes lower bounds (`>=x.y`) by default. Those are not pins; exact versions live only in `uv.lock`. Req 1.9 is met as long as no `==` constraints are passed to `uv add`. The implementer must not hand-edit the dependency arrays.

Hand-written, non-dependency sections of `pyproject.toml` (allowed; the rule only forbids editing dependency lists):

```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = [{ index = "pytorch-cpu", marker = "sys_platform != 'darwin'" }]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
```

`uv.lock` is committed. `uv lock --check` confirms it matches `pyproject.toml`.

### Dockerfile (Req 2)

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# opencv-python-headless needs glib at import time
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

`--no-dev` drops the dev group. The `eval` group is not in uv's default groups (only `dev` is), so it is not installed either (Req 2.2). On Linux, the `torch` source marker selects the CPU wheel. `.dockerignore` excludes `.env`, `.venv`, `__pycache__`, `.pytest_cache` so no secrets enter the image.

### Docker Compose (Req 3)

```yaml
name: screen-to-cart

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: screen_to_cart
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d screen_to_cart"]
      interval: 2s
      timeout: 5s
      retries: 15

  backend:
    build: ./backend
    env_file:
      - .env
    environment:
      # Overrides the localhost URL from .env; inside the network the DB host is "db".
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/screen_to_cart
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

- `env_file: .env` is a reference that Compose resolves at runtime. Nothing in the repo reads, copies or sources `.env` (Req 3.4).
- Values under `environment:` take precedence over `env_file:`, so `DATABASE_URL` points at `db` inside Compose while the user's `.env` keeps `localhost` for running `uv run` on the host.
- The `postgres:postgres` credentials are the local-only defaults already shown in section 5's `DATABASE_URL`; they are not secrets.
- `depends_on: condition: service_healthy` with `pg_isready` makes the backend start after Postgres accepts connections (Req 3.6).

### Environment template (Req 4)

Root `.env.example`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/screen_to_cart

# LLM provider (free tier)
GROQ_API_KEY=
IDENTIFY_VISION_MODEL=groq:qwen/qwen3.8-27b
DISAMBIGUATE_MODEL=groq:openai/gpt-oss-120b
REFINE_MODEL=groq:openai/gpt-oss-20b
# Empty = use REFINE_MODEL
SPONSORSHIP_MODEL=
LLM_MODE=live            # live | record | replay

# Later: ANTHROPIC_API_KEY=

# Tracing
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# Retailers
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
BESTBUY_API_KEY=

# Embeddings
SIGLIP_MODEL=google/siglip-base-patch16-224

# CORS: comma-separated extension origins, e.g. chrome-extension://<extension-id>
CORS_ALLOWED_ORIGINS=
```

Note on the inline comment after `LLM_MODE=live`: python-dotenv (used by pydantic-settings) strips ` # ...` comments on unquoted values, and Compose's `env_file` parser does the same, so the value is `live` in both.

`extension/.env.example`:

```env
# Backend base URL used by the side panel. Defaults to http://localhost:8000 when unset.
WXT_BACKEND_URL=
```

Variables the user must set by hand at the end of Phase 0 (Req 4.7–4.9). The implementer reports this list to the user and never edits `.env`. The same table is committed as the "Setup" section of the root `README.md` (the Setup_Guide), so it serves as both the end-of-phase report and the permanent documentation:

| Variable | File | Where to get the value | Required in Phase 0 |
|---|---|---|---|
| `GROQ_API_KEY` | `.env` | console.groq.com | No (no LLM calls in Phase 0; needed from Phase 2) |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | `.env` | the "Screen to Cart" Langfuse project settings | Yes, for the Phase 0 trace check (Req 14.3); `/health` works without them |
| `CORS_ALLOWED_ORIGINS` | `.env` | `chrome-extension://<id>` from `chrome://extensions` after loading the extension | Yes |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `BESTBUY_API_KEY` | `.env` | the eBay and Best Buy developer portals | No (used from Phase 3) |
| `DATABASE_URL`, `IDENTIFY_VISION_MODEL`, `DISAMBIGUATE_MODEL`, `REFINE_MODEL`, `SPONSORSHIP_MODEL`, `LLM_MODE`, `LANGFUSE_BASE_URL`, `SIGLIP_MODEL` | `.env` | copy the non-secret values from `.env.example` | `DATABASE_URL` yes (host runs of Alembic); the rest no |
| `WXT_BACKEND_URL` | `extension/.env` | the backend URL, only if it is not `http://localhost:8000` | No |

### Settings (`app/config.py`, Req 5)

```python
from pathlib import Path
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"  # repo-root .env; missing file is ignored

LlmMode = Literal["live", "record", "replay"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT_ENV, env_file_encoding="utf-8", extra="ignore",
    )

    database_url: str | None = None

    groq_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None   # optional, for the later switch

    identify_vision_model: str | None = None
    disambiguate_model: str | None = None
    refine_model: str | None = None
    sponsorship_model: str | None = None
    llm_mode: LlmMode = "live"

    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"

    ebay_client_id: SecretStr | None = None
    ebay_client_secret: SecretStr | None = None
    bestbuy_api_key: SecretStr | None = None

    siglip_model: str | None = None

    cors_allowed_origins: Annotated[list[str], NoDecode] = []

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _sponsorship_fallback(self) -> "Settings":
        if not (self.sponsorship_model and self.sponsorship_model.strip()):
            self.sponsorship_model = self.refine_model
        return self

    def model_spec_for(self, role: "Role") -> str | None: ...


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- Env var names map case-insensitively to field names (`IDENTIFY_VISION_MODEL` → `identify_vision_model`).
- Source precedence is the pydantic-settings default, which is not overridden: init kwargs > environment variables > dotenv file > field defaults. A variable set in both the environment and `.env` takes the environment value (Req 5.8). Sources are merged per field, so a variable set only in the environment and another set only in `.env` both load into the same instance (Req 5.9). `settings_customise_sources` is not defined.
- Empty values from `.env` (`GROQ_API_KEY=`) become `None` for optional fields via a shared `mode="before"` validator that turns `""` into `None` for the `str | None` and `SecretStr | None` fields.
- An invalid `LLM_MODE` raises `pydantic.ValidationError` whose error location is `llm_mode` (Req 5.5).
- No field has a model-name or secret default (Req 5.7, 6.8). `langfuse_base_url`'s default is a public URL, not a secret. `siglip_model` has no default because it is a model name; it is unused in Phase 0.
- Secrets are `SecretStr`, so they don't appear in `repr()` or logs.
- Tests build `Settings(_env_file=None, **values)` and never touch `.env` (Req 13.7).
- The application gets Settings through `get_settings()`, which FastAPI uses as a dependency so tests can override it.

### LLM factory (`app/llm/factory.py`, Req 6)

```python
from enum import StrEnum
from langchain_core.language_models.chat_models import BaseChatModel


class Role(StrEnum):
    IDENTIFY_VISION = "identify_vision"
    DISAMBIGUATE = "disambiguate"
    REFINE = "refine"
    SPONSORSHIP = "sponsorship"


class LlmConfigError(ValueError):
    """Bad role, malformed or missing model spec, or unsupported provider."""


class ProviderNotInstalledError(LlmConfigError):
    """Subclass of LlmConfigError: the configured provider's LangChain package is not installed.

    Raised instead of ImportError. The message names the package and the `uv add` command.
    Catching LlmConfigError also catches this error.
    """


def parse_model_spec(spec: str, role: Role) -> tuple[str, str]:
    """Split on the first ':' -> (provider, model). Raises LlmConfigError naming role and spec."""


def get_llm(role: Role | str, settings: Settings | None = None) -> BaseChatModel:
    settings = settings or get_settings()
    role = _coerce_role(role)            # LlmConfigError: "Invalid role 'x'. Valid roles: identify_vision, ..."
    spec = settings.model_spec_for(role) # None/empty -> LlmConfigError naming role and the env var
    provider, model = parse_model_spec(spec, role)
    builder = _BUILDERS.get(provider)    # unknown -> LlmConfigError naming provider and role
    return builder(model, settings)
```

Builders, keyed by provider name:

| Provider | Builder | Notes |
|---|---|---|
| `groq` | `ChatGroq(model=model, api_key=settings.groq_api_key)` | If `groq_api_key` is `None`, raise `LlmConfigError("GROQ_API_KEY is not set (role=...)")` before constructing. Construction sends no request (Req 6.9). The builder and `get_llm` return the constructed `ChatGroq` object itself, with no wrapper, cache or proxy (Req 6.10) |
| `anthropic` | Lazy `import langchain_anthropic` inside the builder. On `ImportError`, raise `ProviderNotInstalledError("Provider 'anthropic' needs langchain-anthropic. Run: uv add langchain-anthropic")`. If installed, return `ChatAnthropic(model=model, api_key=settings.anthropic_api_key)` | Switching later is `uv add` + env change (section 7) |

Parsing rules (Req 6.2, 6.7): `provider, sep, model = spec.partition(":")`, then strip both parts. If `sep` is empty, `provider` is empty or `model` is empty, raise `LlmConfigError(f"Malformed model spec {spec!r} for role {role}: expected 'provider:model'")`. Splitting only on the first `:` keeps model names like `openai/gpt-oss-20b` or a hypothetical `model:tag` intact.

`model_spec_for(role)` maps `identify_vision → identify_vision_model`, `disambiguate → disambiguate_model`, `refine → refine_model`, `sponsorship → sponsorship_model` (already fallen back to refine). The map lives on Settings so the factory holds no field names or model names.

`LLM_MODE` is validated by Settings but the factory ignores it in Phase 0; record/replay wrapping is added in Phase 2.

### Schemas (`app/schemas.py`, Req 8.2, 8.3)

```python
from typing import Literal
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
```

The route declares `response_model=HealthResponse`, so the model appears under `components.schemas.HealthResponse` in `/openapi.json` and in the generated TypeScript types.

### Observability (`app/observability.py`, Req 9)

```python
from contextlib import contextmanager
from collections.abc import Iterator

from langfuse import Langfuse, get_client, observe, propagate_attributes
from langfuse.langchain import CallbackHandler

PROVIDER_TAG = "groq-free"  # Phase 0 constant; becomes a setting when providers change

__all__ = ["init_langfuse", "shutdown_langfuse", "new_callback_handler",
           "trace_attributes", "observe", "PROVIDER_TAG"]


def init_langfuse(settings: Settings) -> Langfuse:
    """Create the process-wide client from Settings. Tracing is disabled when keys are missing."""
    enabled = bool(settings.langfuse_public_key and settings.langfuse_secret_key)
    return Langfuse(
        public_key=_reveal(settings.langfuse_public_key),
        secret_key=_reveal(settings.langfuse_secret_key),
        base_url=settings.langfuse_base_url,   # 'host' on older SDK versions
        tracing_enabled=enabled,
    )


def shutdown_langfuse() -> None:
    get_client().shutdown()   # flushes pending spans; log exceptions (runs at app shutdown, outside any request)


def new_callback_handler() -> CallbackHandler:
    """A new handler on every call. Never cache or share across requests."""
    return CallbackHandler()


@contextmanager
def trace_attributes(trace_name: str, session_id: str | None = None,
                     tags: list[str] | None = None) -> Iterator[None]:
    all_tags = [PROVIDER_TAG, *(t for t in (tags or []) if t != PROVIDER_TAG)]
    with propagate_attributes(trace_name=trace_name, session_id=session_id, tags=all_tags):
        yield
```

- `init_langfuse` runs once in the FastAPI lifespan; later `get_client()` calls in `observe` and `CallbackHandler` return that client.
- Credentials come only from Settings (Req 9.1). The SDK's own env reading is not relied on.
- With missing keys the client has `tracing_enabled=False`, so `observe` and `propagate_attributes` run as no-ops and `/health` returns 200 (Req 9.8).
- The Langfuse SDK exports spans on a background thread, and per its reference, `propagate_attributes` logs and drops invalid values instead of raising. Export failures (bad keys, unreachable host) are logged by the SDK and never reach the request path, which is how `/health` stays 200 (Req 9.9).
- `trace_attributes` has no `try/except`. Only `shutdown_langfuse` catches and logs, because it runs outside the request path.
- `PROVIDER_TAG` is a constant in Phase 0 because only Groq is wired. Section 7 says to change the tag at the switch; making it a setting then is a one-line change and out of scope now.

### FastAPI app (`app/main.py`, Req 8, 9.6)

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_langfuse(settings)   # the app's own Settings, so tests never fall back to get_settings()
        yield
        shutdown_langfuse()

    app = FastAPI(title="Screen to Cart API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        with trace_attributes("health"):
            return await _health_check()

    return app


@observe(name="health")
async def _health_check() -> HealthResponse:
    return HealthResponse(status="ok")


app = create_app()
```

- `trace_attributes` wraps the `@observe()` call, so the root span and everything under it carry `trace_name="health"` and tag `groq-free` (Req 9.6, 9.7).
- `create_app(settings)` lets tests pass their own Settings (CORS origins, disabled Langfuse) without `.env`. The lifespan closes over the same Settings object, so the Langfuse client in tests is built from test values.
- The module-level `app = create_app()` calls `get_settings()` at import time. Tests therefore disable the env file in `tests/conftest.py` before any test module imports `app.main` (see Testing Strategy).
- `/health` touches no LLM, retailer or database (Req 8.6). It reports process liveness only; database readiness is covered by Compose's health check.
- `allow_credentials` stays `False`; the extension sends no cookies.

### Migrations (`app/db/migrations/`, Req 7)

- `alembic.ini` at `backend/` sets `script_location = app/db/migrations` and leaves `sqlalchemy.url` empty.
- `env.py` follows Alembic's async template: `async_engine_from_config` / `create_async_engine(get_settings().database_url, poolclass=NullPool)`, then `connection.run_sync(do_run_migrations)`. If `database_url` is `None` it raises `RuntimeError("DATABASE_URL is not set")`. `target_metadata = None` in Phase 0; Phase 2 points it at the ORM `Base.metadata`.
- `versions/0001_enable_pgvector.py`:

```python
revision = "0001"
down_revision = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
```

`IF NOT EXISTS` makes it succeed when the extension already exists (Req 7.5).

### Extension (Req 10, 11, 12)

Scaffold and packages:

```bash
pnpm dlx wxt@latest init extension --template react --pm pnpm   # non-interactive: React template, pnpm
cd extension
pnpm add @microsoft/fetch-event-source openapi-fetch
pnpm add -D openapi-typescript
```

Then set `"name": "screen-to-cart-extension"` in `package.json` and add the script:

```json
"scripts": {
  "gen:api": "openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts"
}
```

`wxt.config.ts`:

```ts
import { defineConfig } from 'wxt';

export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'Screen to Cart',
    description: 'Find anything you see in a video, compared across stores.',
    permissions: ['sidePanel'],
  },
});
```

WXT generates the `side_panel.default_path` manifest entry from `entrypoints/sidepanel/index.html`. `activeTab`, `scripting` and the YouTube host permission are Phase 1 concerns and are not added yet.

`entrypoints/background.ts` calls `browser.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })` so a toolbar click opens the panel.

`lib/api.ts`:

```ts
import createClient from 'openapi-fetch';
import type { paths } from './api-types';

export const BACKEND_URL: string =
  import.meta.env.WXT_BACKEND_URL || 'http://localhost:8000';

export const api = createClient<paths>({ baseUrl: BACKEND_URL });
```

`lib/api-types.ts` is produced only by `pnpm gen:api` while the backend runs; it is committed so the extension builds without a running backend. `@microsoft/fetch-event-source` is installed but unused until Phase 5.

Side panel status logic, kept pure in `healthStatus.ts` so it is easy to test later:

```ts
export type HealthStatus = 'checking' | 'ok' | 'unreachable';

export function healthStatusFrom(result: { ok: boolean; status?: number } | Error): HealthStatus {
  if (result instanceof Error) return 'unreachable';
  return result.ok && result.status === 200 ? 'ok' : 'unreachable';
}
```

`HealthStatus.tsx` starts in `checking` ("Checking backend…"), calls `api.GET('/health')` once on mount inside a `try/catch`, and renders `backend OK` or "Backend unreachable at {BACKEND_URL}" (Req 12.1–12.4). `App.tsx` renders the product name and `<HealthStatus />`.

## Data Models

| Model | Location | Fields |
|---|---|---|
| `Settings` | `app/config.py` | see Settings section; secrets as `SecretStr \| None` |
| `Role` | `app/llm/factory.py` | `identify_vision`, `disambiguate`, `refine`, `sponsorship` |
| Model spec | string | `"<provider>:<model>"`, split on the first `:` |
| `HealthResponse` | `app/schemas.py` | `status: Literal["ok"]` |
| `HealthStatus` | `extension/entrypoints/sidepanel/healthStatus.ts` | UI state only, not an API payload |

Database: no tables in Phase 0. The only schema change is the `vector` extension.

## Error Handling

| Situation | Behaviour |
|---|---|
| `LLM_MODE` not in `live/record/replay` | `ValidationError` at Settings construction, location `llm_mode`; the app fails fast at startup |
| `get_llm` with a non-role value | `LlmConfigError` naming the value and listing all four roles |
| Role's model spec unset/empty | `LlmConfigError` naming the role and the env var to set (e.g. `REFINE_MODEL`) |
| Malformed spec | `LlmConfigError` naming the role and the spec |
| Unsupported provider | `LlmConfigError` naming the provider, the role and the supported providers |
| `anthropic` without the package | `ProviderNotInstalledError` with `uv add langchain-anthropic` |
| `groq` without `GROQ_API_KEY` | `LlmConfigError` naming `GROQ_API_KEY`; secrets never appear in messages |
| Langfuse keys missing | Client created with `tracing_enabled=False`; `observe` and `propagate_attributes` are no-ops; `/health` returns 200 (Req 9.8) |
| Langfuse unreachable or keys wrong | SDK background exporter logs the failure; request path unaffected; `/health` returns 200 (Req 9.9) |
| `shutdown_langfuse` fails at app shutdown | Logged and swallowed; outside the request path |
| `DATABASE_URL` unset when running Alembic | `RuntimeError("DATABASE_URL is not set")` |
| Postgres not ready | Compose holds the backend until `pg_isready` passes |
| Extension origin not in `CORS_ALLOWED_ORIGINS` | Browser blocks the response; side panel shows "Backend unreachable"; README note tells the user to set the variable |
| Backend down | `fetch` rejects; side panel shows "Backend unreachable at …" |

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Reflection on redundancy: the invalid-role (6.5) and unsupported-provider (6.6) checks share one shape (an unknown name produces an error that names it and its context), so they are combined into one property. Malformed-spec rejection (6.7) stays separate from the parse round trip (6.2) because the generators are disjoint. The groq-construction criteria (6.1, 6.3, 6.9) collapse into one property, as do the CallbackHandler criteria (9.2, 9.3).

### Property 1: Model spec parse round trip

For any non-empty provider string without `:` or surrounding whitespace, and any non-empty model string without surrounding whitespace (including strings containing `/` and `:`), `parse_model_spec(f"{provider}:{model}", role)` returns `(provider, model)` for every Role.

**Validates: Requirements 6.2**

### Property 2: Malformed model specs are rejected

For any string that has no `:`, or whose part before the first `:` is empty or whitespace, or whose part after the first `:` is empty or whitespace, and for any Role, `parse_model_spec` raises `LlmConfigError` whose message contains both the role name and the spec.

**Validates: Requirements 6.7**

### Property 3: Unknown roles and providers produce descriptive errors

For any string that is not one of the four Role values, `get_llm` raises `LlmConfigError` whose message contains that string and all four Role names. For any well-formed spec whose provider is not `groq` or `anthropic`, and any Role configured with that spec, `get_llm` raises `LlmConfigError` whose message contains the provider and the role.

**Validates: Requirements 6.5, 6.6**

### Property 4: Groq specs build an offline ChatGroq for the configured role

For any Role and any non-empty model name, given Settings where that Role's spec is `groq:<model>` and `GROQ_API_KEY` is a test value, `get_llm(role, settings)` returns an object whose exact type is `ChatGroq` (`type(result) is ChatGroq`, so no wrapper or proxy), whose model name equals `<model>` and whose API key equals the test value, and no network connection is opened during the call.

**Validates: Requirements 6.1, 6.3, 6.9, 6.10**

### Property 5: Sponsorship falls back to the refine model

For any refine spec `r` and any sponsorship value `s`, Settings built with `REFINE_MODEL=r` and `SPONSORSHIP_MODEL=s` have `sponsorship_model == r` when `s` is unset, empty or whitespace-only, and `sponsorship_model == s` otherwise.

**Validates: Requirements 5.2, 5.3, 13.3**

### Property 6: LLM_MODE accepts exactly three values

For any string `m`, constructing Settings with `LLM_MODE=m` succeeds with `llm_mode == m` if `m` is one of `live`, `record`, `replay`, and otherwise raises `ValidationError` whose error locations include `llm_mode`.

**Validates: Requirements 5.4, 5.5, 13.3**


### Property 8: CORS origin list parse round trip

For any list of origin strings that contain no commas and no surrounding whitespace, Settings built with `CORS_ALLOWED_ORIGINS` set to the list joined with `,` (optionally with spaces around the commas) have `cors_allowed_origins` equal to the original list, and an empty or whitespace-only value gives an empty list.

**Validates: Requirements 8.5**

## Testing Strategy

### Rules for every test

- No live LLM, retailer or Langfuse calls (Req 13.2). `tests/conftest.py` has an autouse fixture that monkeypatches `socket.socket.connect` to raise unless the address is loopback, so any accidental outbound call fails the test. `respx` stays available for later retailer tests.
- Settings come only from test values: `Settings(_env_file=None, **values)`, or, for the source-precedence test, `Settings(_env_file=<file the test wrote under tmp_path>)`. An autouse fixture clears every Settings-related variable from `os.environ` with `monkeypatch.delenv(..., raising=False)` and calls `get_settings.cache_clear()`, so the developer's shell environment does not leak in (Req 13.7). At module level, before any test imports `app.main`, `conftest.py` also sets `Settings.model_config["env_file"] = None`, so the import-time `app = create_app()` and any `get_settings()` call never open `.env`.
- The app under test is `create_app(test_settings)` (its lifespan uses `test_settings`), and Langfuse is initialised with `tracing_enabled=False`.
- Run with `uv run pytest` (Req 13.1).

### Property tests

There is no PBT library in the planned dev dependencies, so each property test uses `pytest.mark.parametrize` over 100 cases from a generator seeded with a fixed `random.Random(seed)`, so failures reproduce. Generators deliberately include edge cases: `:` inside model names, `/`, unicode, leading/trailing whitespace, upper-case variants of `live`, and the empty string. Each test carries a tag comment:

```python
# Feature: phase-0-setup, Property 1: Model spec parse round trip
```

| Property | Test file | Generator notes |
|---|---|---|
| 1 | `test_llm_factory.py` | provider from `[a-z0-9_-]{1,12}`; model from printable chars incl. `/:.-` |
| 2 | `test_llm_factory.py` | strings with no `:`, `":x"`, `"x:"`, `"  :  "`, random whitespace |
| 3 | `test_llm_factory.py` | random non-role strings; random providers excluding `groq`/`anthropic` |
| 4 | `test_llm_factory.py` | each Role × random model names; socket guard active |
| 5 | `test_config.py` | `s` drawn from `None`, `""`, whitespace, random specs |
| 6 | `test_config.py` | the three valid values plus random strings, `LIVE`, `" live"`, `""` |
| 8 | `test_config.py` | lists of 0–5 `chrome-extension://[a-p]{32}` and `http://localhost:<port>` origins |

### Example and edge-case unit tests

- `anthropic:<model>` with `langchain_anthropic` absent (monkeypatch `sys.modules["langchain_anthropic"] = None`): `ProviderNotInstalledError` mentioning `uv add langchain-anthropic`, and the same call also satisfies `pytest.raises(LlmConfigError)` (Req 6.4, 6.11, 13.8).
- `issubclass(ProviderNotInstalledError, LlmConfigError)` and `ProviderNotInstalledError.__doc__` is non-empty (Req 6.11).
- Settings source precedence (Req 5.8, 5.9): the test writes its own dotenv file under `tmp_path` (e.g. `REFINE_MODEL=groq:from-file` and `DISAMBIGUATE_MODEL=groq:file-only`), sets `REFINE_MODEL=groq:from-env` and `IDENTIFY_VISION_MODEL=groq:env-only` with `monkeypatch.setenv`, then builds `Settings(_env_file=tmp_path / "test.env")`. It asserts `refine_model == "groq:from-env"` (env wins), `disambiguate_model == "groq:file-only"` and `identify_vision_model == "groq:env-only"` (both sources load into one instance). The test never reads the real `.env`.
- `groq` spec with no `GROQ_API_KEY`: `LlmConfigError` naming the variable.
- Role spec unset: error names the role and env var.
- `GET /health` returns 200 and `{"status": "ok"}` with Langfuse disabled (Req 8.2, 9.8, 13.5).
- `/openapi.json` contains `HealthResponse` (Req 8.3).
- The Langfuse trace name, tag and CORS behaviour are checked by hand in the final checkpoint rather than with mocks.

### Smoke and integration checks (manual or scripted, not in `uv run pytest`)

- `uv lock --check` (Req 1.10).
- `docker compose config` shows `DATABASE_URL` with host `db` (Req 3.4).
- `docker compose up`, then `curl localhost:8000/health` returns 200 (Req 3.5, 14.1).
- `docker compose exec db psql -U postgres -d screen_to_cart -c "select extname from pg_extension"` lists `vector`; rerunning `alembic upgrade head` is a no-op (Req 7.4, 7.5).
- `pnpm gen:api` regenerates `lib/api-types.ts`; `pnpm build` succeeds; `pnpm tsc --noEmit` passes.
- Load `extension/.output/chrome-mv3` unpacked, set `CORS_ALLOWED_ORIGINS` in `.env` to its origin, restart the backend, open the side panel: it shows `backend OK` (Req 12, 14.2). With the backend stopped it shows "Backend unreachable".
- With real Langfuse keys, open the side panel and confirm a trace named `health` tagged `groq-free` in the Screen to Cart project (Req 9.7, 14.3). This uses Langfuse units only, no LLM quota.

The extension has no test runner in the plan (section 5 lists none), so the side panel states are checked by hand in Phase 0. `healthStatusFrom` is pure so a Vitest test can be added later without refactoring.
