# Implementation Plan: Phase 0 Setup

## Overview

Build the Phase 0 skeleton in the order of build plan sections 4 and 5: repo hygiene, the env template and the README setup table, the uv backend project, Settings, the LLM factory, the health endpoint with Langfuse tracing, Alembic, Docker, then the WXT extension with generated API types. The plan ends with the `.env` variables the user must set and a manual check of the Phase 0 "Done when" criteria.

Phase 0 is done when `docker compose up` brings up DB + API, the side panel shows "backend OK", and a request shows up as a named trace in Langfuse. Anything that doesn't serve that goal is out of scope.

Scope was trimmed on 2026-10-30 (see the `engineering` steering file). Tasks 1–4 are kept as they were built. From task 5 onward:
- Tests use a few clear examples per behavior. No 100-case parametrized tests, no tests of library behavior, no tests of file contents.
- No error handling for failures that the library already handles or that can't happen in Phase 0.

Rules that apply to every task:
- Python dependencies only via `uv add` / `uv add --dev` / `uv add --group eval`. Extension dependencies only via `pnpm add` / `pnpm add -D`.
- Never read, write, copy or source `.env` or `extension/.env`. New settings go into `.env.example` (no secret values) and `app/config.py`.
- No model-name literals in `backend/app/`.
- Tests never call live LLM, retailer or Langfuse APIs. They build `Settings(_env_file=None, ...)` and run under the socket guard in `tests/conftest.py`.

## Tasks

- [x] 1. Repository hygiene and environment template
  - [x] 1.1 Write `.gitignore` and root `.env.example`
    - `.gitignore` (currently empty): ignore `.env`, `extension/.env`, `extension/.env.*` except `extension/.env.example`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `node_modules/`, `extension/.output/`, `extension/.wxt/`. Keep `!.env.example` so the template is committed
    - Create `.env.example` with exactly the content in the design's "Environment template" section: the section 5 variables with their non-secret example values, empty secrets, `SPONSORSHIP_MODEL=` with no value, `# Later: ANTHROPIC_API_KEY=`, and `CORS_ALLOWED_ORIGINS=`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.5_

  - [x] 1.2 Write the root `README.md` "Setup" section (the Setup_Guide)
    - Create `README.md` with a "Setup" section containing the design's variables table with columns Variable | File | Where to get the value | Required in Phase 0
    - List every non-commented variable in `.env.example` and `extension/.env.example` (including `WXT_BACKEND_URL`), plus the note that the user sets `CORS_ALLOWED_ORIGINS` from the ID in `chrome://extensions`
    - The table is the same list task 11 reports to the user
    - _Requirements: 4.8, 4.9_

- [x] 2. Backend uv project and dependencies
  - [x] 2.1 Initialise the uv project and add the non-dependency `pyproject.toml` sections
    - From the repo root run `uv init backend --app --python 3.12 --name screen-to-cart-backend`; confirm `backend/.python-version` contains `3.12`
    - Delete the template's `backend/main.py` (the app lives in `backend/app/main.py`)
    - Before any `uv add`, add to `backend/pyproject.toml` the `[[tool.uv.index]]` entry `pytorch-cpu` (`https://download.pytorch.org/whl/cpu`, `explicit = true`), `[tool.uv.sources]` mapping `torch` to `pytorch-cpu` with marker `sys_platform != 'darwin'`, `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`) and `[tool.ruff]` (`target-version = "py312"`). These are the only hand-written sections; do not touch `dependencies` or `dependency-groups`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 2.2 Add dependencies with uv in the planned order
    - In `backend/`, run each command from the design's "Backend project setup" section in order: the FastAPI/pydantic group, the LangGraph/LangChain group, `langfuse`, `httpx`, the SQLAlchemy/asyncpg/alembic/pgvector group, `opencv-python-headless pillow numpy torch transformers sentencepiece`, `rapidfuzz`, then `uv add --dev pytest pytest-asyncio respx ruff mypy` and `uv add --group eval pandas matplotlib`
    - Pass no `==` pins; let uv write lower bounds and resolve exact versions in `uv.lock`
    - Run `uv lock --check` and confirm it passes; `backend/uv.lock` is committed
    - _Requirements: 1.6, 1.7, 1.8, 1.9, 1.10_

  - [x] 2.3 Create the backend package layout
    - Create `backend/app/__init__.py`, `backend/app/llm/__init__.py`, `backend/app/db/__init__.py` and `backend/tests/` (empty `__init__.py` files where needed for imports)
    - Run `uv run python -c "import fastapi, langgraph, langchain_groq, langfuse, torch"` to confirm the environment resolves
    - _Requirements: 8.1_

- [x] 3. Settings
  - [x] 3.1 Implement `backend/app/config.py`
    - `Settings(BaseSettings)` reading the repo-root `.env` path (missing file ignored) with `extra="ignore"`, fields exactly as in the design's Settings section; secrets as `SecretStr | None`; no model-name or secret defaults
    - Shared `mode="before"` validator turning `""` into `None` for optional `str`/`SecretStr` fields
    - `llm_mode: Literal["live", "record", "replay"] = "live"`
    - `cors_allowed_origins: Annotated[list[str], NoDecode]` with a comma-split, strip, drop-empty validator
    - `model_validator(mode="after")` that falls back `sponsorship_model` to `refine_model` when unset, empty or whitespace-only
    - `model_spec_for(role)` mapping each Role to its field; `get_settings()` with `@lru_cache`
    - Keep the pydantic-settings default source order (environment over dotenv, merged per field); do not define `settings_customise_sources`
    - _Requirements: 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 8.5_

  - [x] 3.2 Write `backend/tests/conftest.py` with the test isolation fixtures
    - At module level (before any test module imports `app.main`), set `Settings.model_config["env_file"] = None` so the import-time `app = create_app()` and every `get_settings()` call never open `.env`
    - Autouse fixture that monkeypatches `socket.socket.connect` (and `connect_ex`) to raise unless the address is loopback, so any outbound call fails the test
    - Autouse fixture that `monkeypatch.delenv(..., raising=False)` every Settings variable (all fields, upper-case) and calls `get_settings.cache_clear()` before and after each test
    - `make_settings(**values)` fixture returning `Settings(_env_file=None, **values)`; nothing opens `.env`
    - _Requirements: 13.1, 13.2, 13.7_

  - [x] 3.3 Write property test for the sponsorship fallback in `tests/test_config.py`
    - **Property 5: Sponsorship falls back to the refine model**
    - Generator: `s` from `None`, `""`, whitespace-only strings and random `provider:model` specs
    - **Validates: Requirements 5.2, 5.3, 13.3**

  - [x] 3.4 Write property test for `LLM_MODE` validation in `tests/test_config.py`
    - **Property 6: LLM_MODE accepts exactly three values**
    - Generator: `live`, `record`, `replay` plus random strings, `LIVE`, `" live"`, `""`; invalid values raise `ValidationError` with `llm_mode` in the error locations
    - **Validates: Requirements 5.4, 5.5, 13.3**

  - [x] 3.5 Write property test for CORS origin parsing in `tests/test_config.py`
    - **Property 8: CORS origin list parse round trip**
    - Generator: lists of 0–5 `chrome-extension://[a-p]{32}` and `http://localhost:<port>` origins, joined with `,` with optional spaces; empty and whitespace-only values give `[]`
    - **Validates: Requirements 8.5**

  - [x] 3.6 Write unit test for Settings source precedence in `tests/test_config.py`
    - Write a test dotenv file under `tmp_path` (e.g. `REFINE_MODEL=groq:from-file`, `DISAMBIGUATE_MODEL=groq:file-only`); `monkeypatch.setenv` `REFINE_MODEL=groq:from-env` and `IDENTIFY_VISION_MODEL=groq:env-only`; build `Settings(_env_file=tmp_path / "test.env")`
    - Assert the env value wins for `refine_model`, and that the env-only and file-only values both load into the same instance
    - Never reads the real `.env`
    - _Requirements: 5.8, 5.9, 13.7_

- [x] 4. LLM provider factory
  - [x] 4.1 Implement `backend/app/llm/factory.py` and re-export from `backend/app/llm/__init__.py`
    - `Role(StrEnum)` with the four roles; `LlmConfigError(ValueError)`; `ProviderNotInstalledError(LlmConfigError)`, a documented subclass (non-empty docstring)
    - `parse_model_spec(spec, role)` using `str.partition(":")` and stripping both parts; malformed specs raise `LlmConfigError` naming the role and the spec
    - `get_llm(role, settings=None)`: coerce role (error names the value and lists all roles), read `settings.model_spec_for(role)` (unset → error naming the role and its env var), parse, dispatch to `_BUILDERS` (unknown provider → error naming provider, role and supported providers)
    - `groq` builder: raise `LlmConfigError` naming `GROQ_API_KEY` if unset, else return `ChatGroq(model=..., api_key=...)`; no request is sent at construction; the constructed `ChatGroq` is returned as is, with no wrapper, cache or proxy
    - `anthropic` builder: lazy `import langchain_anthropic`; on `ImportError` raise `ProviderNotInstalledError` with `uv add langchain-anthropic`
    - Ignore `LLM_MODE` in Phase 0; no model-name literals anywhere in the module; secrets never appear in error messages
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11_

  - [x] 4.2 Write property test for spec parsing in `tests/test_llm_factory.py`
    - **Property 1: Model spec parse round trip**
    - Generator: provider from `[a-z0-9_-]{1,12}`, model from printable chars including `/`, `:`, `.`, `-`, across every Role
    - **Validates: Requirements 6.2**

  - [x] 4.3 Write property test for malformed specs in `tests/test_llm_factory.py`
    - **Property 2: Malformed model specs are rejected**
    - Generator: strings without `:`, `":x"`, `"x:"`, `"  :  "`, random whitespace around the separator
    - **Validates: Requirements 6.7**

  - [x] 4.4 Write property test for unknown roles and providers in `tests/test_llm_factory.py`
    - **Property 3: Unknown roles and providers produce descriptive errors**
    - Generator: random non-role strings; random provider names excluding `groq` and `anthropic`
    - **Validates: Requirements 6.5, 6.6**

  - [x] 4.5 Write property test for Groq construction in `tests/test_llm_factory.py`
    - **Property 4: Groq specs build an offline ChatGroq for the configured role**
    - Each Role × random model names with a dummy `GROQ_API_KEY`; assert `type(result) is ChatGroq` and the model name and key on it; the socket guard proves no connection is opened
    - **Validates: Requirements 6.1, 6.3, 6.9, 6.10**

  - [x] 4.6 Write unit tests for factory error cases in `tests/test_llm_factory.py`
    - `anthropic:<model>` with `sys.modules["langchain_anthropic"] = None` raises `ProviderNotInstalledError` (asserted with `pytest.raises(ProviderNotInstalledError)`) mentioning `uv add langchain-anthropic`, and the same call also satisfies `pytest.raises(LlmConfigError)`
    - `issubclass(ProviderNotInstalledError, LlmConfigError)` and `ProviderNotInstalledError.__doc__` is non-empty
    - `groq` spec with no `GROQ_API_KEY` raises `LlmConfigError` naming the variable
    - Role spec unset raises an error naming the role and env var (e.g. `REFINE_MODEL`)
    - Unsupported provider and malformed spec cases are covered by 4.3 and 4.4; together 4.2–4.6 cover every case in Req 13.4
    - _Requirements: 6.4, 6.11, 13.4, 13.8_

- [x] 5. Checkpoint: backend checks pass
  - In `backend/`: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy app`. Fix anything that fails.

- [x] 6. Health endpoint with Langfuse tracing
  - [x] 6.1 Add `HealthResponse` to `backend/app/schemas.py`
    - `HealthResponse(BaseModel)` with `status: Literal["ok"]`
    - _Requirements: 8.2, 8.3_

  - [x] 6.2 Implement `backend/app/observability.py`
    - `init_langfuse(settings)`: build `Langfuse(...)` from Settings, with `tracing_enabled=False` when either key is missing. Check the installed SDK for the base URL keyword (`base_url`, older alias `host`)
    - `shutdown_langfuse()`: `get_client().shutdown()`, logging instead of raising on failure
    - `new_callback_handler()`: return a new `CallbackHandler` on every call
    - `trace_attributes(trace_name, session_id=None, tags=None)`: context manager around `propagate_attributes`, with `PROVIDER_TAG = "groq-free"` first in the tags
    - Re-export `observe`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.8, 9.9_

  - [x] 6.3 Implement `backend/app/main.py`
    - `create_app(settings=None)` with a `lifespan` that calls `init_langfuse(settings)` on startup and `shutdown_langfuse()` on shutdown
    - Title "Screen to Cart API"; `CORSMiddleware` with `settings.cors_allowed_origins`, methods `GET`/`POST`, `allow_credentials=False`
    - `GET /health` with `response_model=HealthResponse`, running inside `trace_attributes("health")` and an `@observe(name="health")` function. No LLM, retailer or DB calls
    - Module-level `app = create_app()`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.6, 9.7, 9.8, 9.9_

  - [x] 6.4 Write `backend/tests/test_health.py`
    - With Langfuse disabled, `GET /health` returns 200 and `{"status": "ok"}`. Use `with TestClient(create_app(settings))` so the lifespan runs with test settings
    - `/openapi.json` contains `HealthResponse`
    - _Requirements: 8.2, 8.3, 13.5_

- [x] 7. Alembic with the pgvector migration
  - In `backend/`: `uv run alembic init -t async app/db/migrations`; keep `alembic.ini` in `backend/` with `script_location = app/db/migrations` and an empty `sqlalchemy.url`
  - `env.py`: async engine from `get_settings().database_url` with `NullPool`; raise `RuntimeError("DATABASE_URL is not set")` when unset; `target_metadata = None`
  - `versions/0001_enable_pgvector.py` (`revision = "0001"`): `CREATE EXTENSION IF NOT EXISTS vector`, and `DROP EXTENSION IF EXISTS vector` on downgrade
  - Confirm `uv run alembic history` lists `0001` (needs no database)
  - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [x] 8. Docker image and Compose stack
  - `backend/.dockerignore`: `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
  - `backend/Dockerfile` as in the design: `python:3.12-slim`, uv from `ghcr.io/astral-sh/uv`, `libglib2.0-0`, `uv sync --frozen --no-dev` (`--no-install-project` first for layer caching), `CMD` runs `alembic upgrade head` then `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  - `docker-compose.yml`: `name: screen-to-cart`; `db` on `pgvector/pgvector:pg16` with `POSTGRES_DB: screen_to_cart`, port 5432, a `pgdata` volume and a `pg_isready` healthcheck; `backend` built from `./backend` with `env_file: [.env]`, `environment.DATABASE_URL` pointing at host `db`, port 8000, `depends_on.db.condition: service_healthy`
  - Run `docker build -t screen-to-cart-backend backend` and confirm it builds
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.6_

- [x] 9. Extension
  - [x] 9.1 Scaffold the WXT React extension and add packages
    - From the repo root: `pnpm dlx wxt@latest init extension --template react --pm pnpm`. If the installed WXT rejects these flags, stop and ask the user to run `pnpm dlx wxt@latest init extension` and pick React + pnpm
    - In `extension/package.json`: set `"name": "screen-to-cart-extension"` and add the script `"gen:api": "openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts"`
    - In `extension/`: `pnpm add @microsoft/fetch-event-source openapi-fetch` and `pnpm add -D openapi-typescript`
    - Remove the template's `popup` and `content` entrypoints
    - Create `extension/.env.example` with only the `WXT_BACKEND_URL=` line and its comment from the design
    - _Requirements: 10.1, 10.2, 10.5, 10.6, 10.7, 11.3, 11.5_

  - [x] 9.2 Configure the manifest and background script
    - `wxt.config.ts`: React module, `manifest.name = "Screen to Cart"`, `manifest.description = "Find anything you see in a video, compared across stores."`, `permissions: ["sidePanel"]`
    - `entrypoints/background.ts`: `browser.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })`
    - _Requirements: 10.3, 10.4, 10.8_

  - [x] 9.3 Generate `extension/lib/api-types.ts`
    - Start `uv run uvicorn app.main:app --port 8000` in `backend/` as a background process, run `pnpm gen:api` in `extension/`, then stop the process. Commit the generated file
    - If the backend can't start in the agent environment, stop and ask the user to run the two commands
    - _Requirements: 11.1, 11.2_

  - [x] 9.4 Implement the typed client in `extension/lib/api.ts`
    - `BACKEND_URL` from `import.meta.env.WXT_BACKEND_URL`, falling back to `http://localhost:8000`; `api = createClient<paths>({ baseUrl: BACKEND_URL })`
    - _Requirements: 11.2, 11.4, 11.5_

  - [x] 9.5 Build the side panel health check
    - `entrypoints/sidepanel/index.html` and `main.tsx` mounting `<App />`
    - `healthStatus.ts` with the `HealthStatus` type and `healthStatusFrom(result)` from the design
    - `HealthStatus.tsx`: shows "Checking backend…", calls `api.GET('/health')` once on mount, then shows `backend OK` or "Backend unreachable at {BACKEND_URL}"
    - `App.tsx`: "Screen to Cart" heading and `<HealthStatus />`
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 10. Checkpoint: all automated checks pass
  - Backend: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy app`. Extension: `pnpm build`, `pnpm exec tsc --noEmit`. Confirm `git ls-files` lists no `.env` file. Fix anything that fails.

- [ ] 11. Tell the user which variables to set
  - Don't open `.env`. Point the user to the README "Setup" table and list what to set after copying `.env.example` to `.env`:
    - `GROQ_API_KEY` (console.groq.com)
    - `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (the "Screen to Cart" Langfuse project)
    - `CORS_ALLOWED_ORIGINS=chrome-extension://<id>`, using the ID from `chrome://extensions` after loading the unpacked extension
    - `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `BESTBUY_API_KEY`: optional until Phase 3
    - Optional `WXT_BACKEND_URL` in `extension/.env`, only if the backend isn't on `http://localhost:8000`
  - _Requirements: 4.7, 4.8_

- [ ] 12. Final checkpoint: Phase 0 "Done when" (the user runs these)
  - These need the user's `.env` and Chrome, so the agent gives the commands and waits for the results.
  - `docker compose up --build`, then `curl localhost:8000/health` returns `{"status":"ok"}` (Req 3.5, 14.1)
  - `docker compose exec db psql -U postgres -d screen_to_cart -c "select extname from pg_extension"` lists `vector` (Req 7.4)
  - Load `extension/.output/chrome-mv3` unpacked, set `CORS_ALLOWED_ORIGINS`, restart the backend, click the toolbar icon: the side panel shows `backend OK`. With the backend stopped it shows "Backend unreachable" (Req 12.2, 12.3, 14.2)
  - In Langfuse, a trace named `health` tagged `groq-free` appears in the Screen to Cart project (Req 9.7, 14.3)

## Notes

- Tasks 3.3–3.5 and 4.2–4.5 were written as 100-case parametrized tests before the scope trim. They pass and stay as they are; don't extend that pattern.
- The extension has no test runner in Phase 0.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3"] },
    { "id": 4, "tasks": ["3.1"] },
    { "id": 5, "tasks": ["3.2", "4.1", "6.1"] },
    { "id": 6, "tasks": ["3.3", "4.2", "6.2", "7"] },
    { "id": 7, "tasks": ["3.4", "4.3", "6.3"] },
    { "id": 8, "tasks": ["3.5", "4.4", "6.4", "8"] },
    { "id": 9, "tasks": ["3.6", "4.5", "9.1"] },
    { "id": 10, "tasks": ["4.6", "9.2"] },
    { "id": 11, "tasks": ["9.3"] },
    { "id": 12, "tasks": ["9.4"] },
    { "id": 13, "tasks": ["9.5"] },
    { "id": 14, "tasks": ["11"] }
  ]
}
```
