# Implementation Plan: Phase 0 Setup

## Overview

Build the Phase 0 skeleton in the order of build plan sections 4 and 5: repo hygiene, the env template and the README setup table, the uv backend project (index and torch source before `torch` is added), Settings, the LLM factory, schemas, observability, the FastAPI app, Alembic, Docker, then the WXT extension with generated API types. The plan ends with an automated checkpoint, a report of the `.env` variables the user must set, and a manual verification checkpoint for the Phase 0 "Done when" criteria.

Rules that apply to every task:
- Python dependencies only via `uv add` / `uv add --dev` / `uv add --group eval`. Extension dependencies only via `pnpm add` / `pnpm add -D`. Never hand-edit dependency arrays in `pyproject.toml` or `package.json`.
- Never read, write, copy or source `.env` or `extension/.env`. New settings go into `.env.example` (no secret values) and `app/config.py`.
- No model-name literals in `backend/app/`. Model names live only in `.env.example` and the user's `.env`.
- Tests never call live LLM, retailer or Langfuse APIs. They build `Settings(_env_file=None, ...)` and run under the loopback-only socket guard in `tests/conftest.py`.
- Property tests use `pytest.mark.parametrize` over 100 cases from a fixed-seed `random.Random`, with no `hypothesis`, and carry the comment `# Feature: phase-0-setup, Property N: <title>`.

## Tasks

- [x] 1. Repository hygiene and environment template
  - [x] 1.1 Write `.gitignore` and root `.env.example`
    - `.gitignore` (currently empty): ignore `.env`, `extension/.env`, `extension/.env.*` except `extension/.env.example`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `node_modules/`, `extension/.output/`, `extension/.wxt/`. Keep `!.env.example` so the template is committed
    - Create `.env.example` with exactly the content in the design's "Environment template" section: the section 5 variables with their non-secret example values, empty secrets, `SPONSORSHIP_MODEL=` with no value, `# Later: ANTHROPIC_API_KEY=`, and `CORS_ALLOWED_ORIGINS=`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.5_

  - [x] 1.2 Write the root `README.md` "Setup" section (the Setup_Guide)
    - Create `README.md` with a "Setup" section containing the design's variables table with columns Variable | File | Where to get the value | Required in Phase 0
    - List every non-commented variable in `.env.example` and `extension/.env.example` (including `WXT_BACKEND_URL`), plus the note that the user sets `CORS_ALLOWED_ORIGINS` from the ID in `chrome://extensions`
    - The table is the same list task 12.1 reports to the user
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

- [ ] 4. LLM provider factory
  - [ ] 4.1 Implement `backend/app/llm/factory.py` and re-export from `backend/app/llm/__init__.py`
    - `Role(StrEnum)` with the four roles; `LlmConfigError(ValueError)`; `ProviderNotInstalledError(LlmConfigError)`, a documented subclass (non-empty docstring)
    - `parse_model_spec(spec, role)` using `str.partition(":")` and stripping both parts; malformed specs raise `LlmConfigError` naming the role and the spec
    - `get_llm(role, settings=None)`: coerce role (error names the value and lists all roles), read `settings.model_spec_for(role)` (unset → error naming the role and its env var), parse, dispatch to `_BUILDERS` (unknown provider → error naming provider, role and supported providers)
    - `groq` builder: raise `LlmConfigError` naming `GROQ_API_KEY` if unset, else return `ChatGroq(model=..., api_key=...)`; no request is sent at construction; the constructed `ChatGroq` is returned as is, with no wrapper, cache or proxy
    - `anthropic` builder: lazy `import langchain_anthropic`; on `ImportError` raise `ProviderNotInstalledError` with `uv add langchain-anthropic`
    - Ignore `LLM_MODE` in Phase 0; no model-name literals anywhere in the module; secrets never appear in error messages
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11_

  - [ ]* 4.2 Write property test for spec parsing in `tests/test_llm_factory.py`
    - **Property 1: Model spec parse round trip**
    - Generator: provider from `[a-z0-9_-]{1,12}`, model from printable chars including `/`, `:`, `.`, `-`, across every Role
    - **Validates: Requirements 6.2**

  - [ ]* 4.3 Write property test for malformed specs in `tests/test_llm_factory.py`
    - **Property 2: Malformed model specs are rejected**
    - Generator: strings without `:`, `":x"`, `"x:"`, `"  :  "`, random whitespace around the separator
    - **Validates: Requirements 6.7**

  - [ ]* 4.4 Write property test for unknown roles and providers in `tests/test_llm_factory.py`
    - **Property 3: Unknown roles and providers produce descriptive errors**
    - Generator: random non-role strings; random provider names excluding `groq` and `anthropic`
    - **Validates: Requirements 6.5, 6.6**

  - [ ]* 4.5 Write property test for Groq construction in `tests/test_llm_factory.py`
    - **Property 4: Groq specs build an offline ChatGroq for the configured role**
    - Each Role × random model names with a dummy `GROQ_API_KEY`; assert `type(result) is ChatGroq` and the model name and key on it; the socket guard proves no connection is opened
    - **Validates: Requirements 6.1, 6.3, 6.9, 6.10**

  - [ ]* 4.6 Write unit tests for factory error cases in `tests/test_llm_factory.py`
    - `anthropic:<model>` with `sys.modules["langchain_anthropic"] = None` raises `ProviderNotInstalledError` (asserted with `pytest.raises(ProviderNotInstalledError)`) mentioning `uv add langchain-anthropic`, and the same call also satisfies `pytest.raises(LlmConfigError)`
    - `issubclass(ProviderNotInstalledError, LlmConfigError)` and `ProviderNotInstalledError.__doc__` is non-empty
    - `groq` spec with no `GROQ_API_KEY` raises `LlmConfigError` naming the variable
    - Role spec unset raises an error naming the role and env var (e.g. `REFINE_MODEL`)
    - Unsupported provider and malformed spec cases are covered by 4.3 and 4.4; together 4.2–4.6 cover every case in Req 13.4
    - _Requirements: 6.4, 6.11, 13.4, 13.8_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Run `uv run pytest` and `uv run ruff check .` in `backend/`. Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Schemas, observability and the FastAPI app
  - [ ] 6.1 Implement `backend/app/schemas.py`
    - `HealthResponse(BaseModel)` with `status: Literal["ok"]`
    - _Requirements: 8.2, 8.3_

  - [ ] 6.2 Implement `backend/app/observability.py`
    - `init_langfuse(settings)` building `Langfuse(...)` from Settings only, with `tracing_enabled=False` when either key is missing; check the installed SDK for the base URL keyword (`base_url`, older alias `host`)
    - `shutdown_langfuse()` flushing via `get_client().shutdown()` and logging, not raising, on failure
    - `new_callback_handler()` returning a new `langfuse.langchain.CallbackHandler` every call
    - `trace_attributes(trace_name, session_id=None, tags=None)` context manager wrapping `propagate_attributes` with `PROVIDER_TAG = "groq-free"` first in the tags
    - Re-export `observe`
    - No try/except inside `trace_attributes` around `propagate_attributes`; setup errors propagate. Only `shutdown_langfuse` catches, because it runs outside the request path
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.8, 9.9, 9.10_

  - [ ] 6.3 Implement `backend/app/main.py`
    - `create_app(settings=None)` resolves `settings = settings or get_settings()` and defines a `lifespan` closure calling `init_langfuse(settings)` on startup and `shutdown_langfuse()` on shutdown, so tests' Settings drive Langfuse
    - `FastAPI` with title "Screen to Cart API", `CORSMiddleware` using `settings.cors_allowed_origins`, methods `GET`/`POST`, `allow_credentials=False`
    - `GET /health` with `response_model=HealthResponse`, running `_health_check()` (decorated `@observe(name="health")`) inside `trace_attributes("health")`; no LLM, retailer or DB calls
    - No try/except around `trace_attributes`/`propagate_attributes` or `observe` on the request path, so a tracing setup failure returns 500 instead of a 200 without tracing
    - Module-level `app = create_app()`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.6, 9.7, 9.8, 9.9, 9.10_

  - [ ]* 6.4 Write property test for CallbackHandler distinctness in `tests/test_observability.py`
    - **Property 7: Each call returns a new CallbackHandler**
    - `n` in 2..20 with Langfuse disabled; assert pairwise distinct `id()` and `isinstance(..., CallbackHandler)`
    - **Validates: Requirements 9.2, 9.3, 13.6**

  - [ ]* 6.5 Write unit tests for the health endpoint, OpenAPI, CORS and trace attributes
    - `tests/test_health.py`: `GET /health` returns 200 and `{"status": "ok"}` with Langfuse disabled, and again with dummy keys and an unroutable `LANGFUSE_BASE_URL` (socket guard blocks export); `/openapi.json` contains `HealthResponse`; preflight `OPTIONS /health` echoes an allowed origin and omits the header for a disallowed one. Use `create_app(test_settings)` inside `with TestClient(app)` so the lifespan runs with `test_settings`
    - `tests/test_health.py`: monkeypatch `app.observability.propagate_attributes` with a stub that raises `RuntimeError`, call `GET /health` through `TestClient(app, raise_server_exceptions=False)` and assert status 500
    - `tests/test_observability.py`: patch `propagate_attributes` and assert `trace_attributes("health")` passes `trace_name="health"` and tags containing `groq-free`
    - _Requirements: 8.2, 8.3, 8.4, 9.4, 9.6, 9.8, 9.9, 9.10, 13.5_

- [ ] 7. Database migrations
  - [ ] 7.1 Set up Alembic with the async template and the pgvector migration
    - In `backend/` run `uv run alembic init -t async app/db/migrations`, move/keep `alembic.ini` at `backend/` with `script_location = app/db/migrations` and an empty `sqlalchemy.url`
    - Edit `env.py` to build the async engine from `get_settings().database_url` with `NullPool`, raising `RuntimeError("DATABASE_URL is not set")` when unset; `target_metadata = None`
    - Add `versions/0001_enable_pgvector.py` (`revision = "0001"`, `down_revision = None`) running `CREATE EXTENSION IF NOT EXISTS vector` and `DROP EXTENSION IF EXISTS vector` on downgrade
    - Confirm `uv run alembic history` lists `0001` (offline; needs no database)
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [ ] 8. Docker image and Compose stack
  - [ ] 8.1 Write `backend/.dockerignore` and `backend/Dockerfile`
    - `.dockerignore` excludes `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
    - Dockerfile exactly as in the design: `python:3.12-slim`, uv copied from `ghcr.io/astral-sh/uv`, `libglib2.0-0`, two-step `uv sync --frozen --no-dev` (with `--no-install-project` first), `CMD` running `alembic upgrade head` then `uvicorn app.main:app --host 0.0.0.0 --port 8000`
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 8.2 Write `docker-compose.yml`
    - `name: screen-to-cart`; `db` service on `pgvector/pgvector:pg16` with `POSTGRES_DB: screen_to_cart`, port 5432, `pgdata` volume and a `pg_isready` healthcheck
    - `backend` service built from `./backend`, `env_file: [.env]` by reference, `environment.DATABASE_URL` overriding the host to `db`, port 8000, `depends_on.db.condition: service_healthy`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6_

  - [ ]* 8.3 Write repository hygiene tests in `tests/test_repo_hygiene.py`
    - `.env.example` has every required name, keeps the non-secret values, leaves secrets empty, has `SPONSORSHIP_MODEL=` and `# Later: ANTHROPIC_API_KEY=` (reads `.env.example` only, never `.env`)
    - `README.md` has a "Setup" section whose table lists every non-commented variable in `.env.example` and `extension/.env.example`
    - No file under `backend/app/` contains `qwen/`, `gpt-oss`, `claude-` or `siglip-`
    - `pyproject.toml` contains the `pytorch-cpu` index and the `torch` source
    - _Requirements: 1.3, 1.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.8, 4.9, 6.8_

- [ ] 9. Checkpoint - Ensure all backend tests pass
  - Run `uv run pytest`, `uv run ruff check .` and `uv lock --check` in `backend/`. Run `docker build -t screen-to-cart-backend backend` and confirm `docker run --rm screen-to-cart-backend python -c "import pytest"` and `... "import pandas"` both fail (dev and eval groups excluded). Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Extension
  - [ ] 10.1 Scaffold the WXT React extension and add packages
    - From the repo root run `pnpm dlx wxt@latest init extension --template react --pm pnpm` (non-interactive; if the installed WXT rejects these flags, stop and ask the user to run `pnpm dlx wxt@latest init extension` and pick React + pnpm)
    - Set `"name": "screen-to-cart-extension"` in `extension/package.json` and add the script `"gen:api": "openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts"` (scripts are not dependency fields)
    - In `extension/` run `pnpm add @microsoft/fetch-event-source openapi-fetch` and `pnpm add -D openapi-typescript`; `pnpm-lock.yaml` is committed
    - Remove the template's `popup` and `content` entrypoints
    - Create `extension/.env.example` containing only the `WXT_BACKEND_URL=` line and its comment from the design
    - _Requirements: 10.1, 10.2, 10.5, 10.6, 10.7, 11.3, 11.5_

  - [ ] 10.2 Configure the manifest and background script
    - `extension/wxt.config.ts`: React module, `manifest.name = "Screen to Cart"`, `manifest.description = "Find anything you see in a video, compared across stores."`, `permissions: ["sidePanel"]`
    - `extension/entrypoints/background.ts`: `browser.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })`
    - _Requirements: 10.3, 10.4, 10.8_

  - [ ] 10.3 Generate `extension/lib/api-types.ts` from the running backend
    - Start the backend as a background process (`uv run uvicorn app.main:app --port 8000` in `backend/`, via the background-process tool), run `pnpm gen:api` in `extension/`, then stop the process
    - Never edit `lib/api-types.ts` by hand; commit the generated file so the extension builds without a running backend
    - If the backend cannot start in the agent environment, stop and ask the user to run the two commands
    - _Requirements: 11.1, 11.2_

  - [ ] 10.4 Implement the typed client in `extension/lib/api.ts`
    - `BACKEND_URL` from `import.meta.env.WXT_BACKEND_URL` with fallback `http://localhost:8000`; `api = createClient<paths>({ baseUrl: BACKEND_URL })`
    - No hand-written payload types; import only from `./api-types`
    - _Requirements: 11.2, 11.4, 11.5_

  - [ ] 10.5 Build the side panel health check
    - `entrypoints/sidepanel/index.html` and `main.tsx` mounting `<App />`
    - `healthStatus.ts`: `HealthStatus` type and pure `healthStatusFrom(result)` as in the design
    - `HealthStatus.tsx`: starts in `checking` ("Checking backend…"), calls `api.GET('/health')` once on mount in `try/catch`, renders `backend OK` or "Backend unreachable at {BACKEND_URL}"
    - `App.tsx`: renders "Screen to Cart" and `<HealthStatus />`; one component per file
    - Run `pnpm build` and `pnpm exec tsc --noEmit` in `extension/` and confirm both pass
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [ ] 11. Checkpoint - Ensure all automated checks pass
  - Backend: `uv run pytest`, `uv run ruff check .`, `uv lock --check`. Extension: `pnpm build`, `pnpm exec tsc --noEmit`. Confirm `git status` shows no `.env` file staged or tracked. Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Hand-off to the user
  - [ ] 12.1 Report the variables the user must set by hand
    - Do not open or modify `.env` or `extension/.env`. Report the same list as the `README.md` "Setup" table (task 1.2) and point the user to it. Tell the user to create `.env` from `.env.example` and set:
      - `GROQ_API_KEY` (console.groq.com)
      - `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (the "Screen to Cart" Langfuse project)
      - `CORS_ALLOWED_ORIGINS=chrome-extension://<id>` using the ID shown in `chrome://extensions` after loading the unpacked extension
      - `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `BESTBUY_API_KEY`: optional until Phase 3
      - Non-secret values (`DATABASE_URL`, model specs, `LLM_MODE`, `LANGFUSE_BASE_URL`, `SIGLIP_MODEL`) copied from `.env.example`
      - Optional `WXT_BACKEND_URL` in `extension/.env`, only if the backend is not on `http://localhost:8000`
    - _Requirements: 4.7, 4.8_

- [ ] 13. Final checkpoint - Phase 0 "Done when" (manual verification by the user)
  - These steps need the user's `.env` values and Chrome, so the user runs them; the agent only provides the commands and waits for results.
  - **Manual (user):** `docker compose up --build`; confirm both services start, then `curl localhost:8000/health` returns `{"status":"ok"}` (Req 3.5, 14.1)
  - **Manual (user):** `docker compose config` shows `DATABASE_URL` with host `db` (Req 3.4); `docker compose exec db psql -U postgres -d screen_to_cart -c "select extname from pg_extension"` lists `vector`, and `docker compose exec backend alembic upgrade head` is a no-op on rerun (Req 7.4, 7.5)
  - **Manual (user):** load `extension/.output/chrome-mv3` unpacked in Chrome, set `CORS_ALLOWED_ORIGINS` to its origin, restart the backend, click the toolbar icon: the side panel shows `backend OK`; with the backend stopped it shows "Backend unreachable" (Req 12.2, 12.3, 14.2)
  - **Manual (user):** with real Langfuse keys, open the side panel and confirm a trace named `health` tagged `groq-free` in the Screen to Cart project. This uses Langfuse units only, no LLM quota (Req 9.7, 14.3)
  - Ensure all checks pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster setup; the core implementation tasks are not optional.
- Property tests use seeded `pytest.mark.parametrize` instead of `hypothesis` to stay within the section 5 dev dependency list.
- `docker compose` commands need the user's `.env` (referenced by `env_file`), so they are in the manual checkpoint rather than the automated one.
- The extension has no test runner in Phase 0; `healthStatusFrom` is pure so a Vitest test can be added later.

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
    { "id": 6, "tasks": ["3.3", "4.2", "6.2", "7.1"] },
    { "id": 7, "tasks": ["3.4", "4.3", "6.3"] },
    { "id": 8, "tasks": ["3.5", "4.4", "6.4", "8.1"] },
    { "id": 9, "tasks": ["3.6", "4.5", "6.5", "8.2"] },
    { "id": 10, "tasks": ["4.6", "10.1"] },
    { "id": 11, "tasks": ["8.3", "10.2"] },
    { "id": 12, "tasks": ["10.3"] },
    { "id": 13, "tasks": ["10.4"] },
    { "id": 14, "tasks": ["10.5"] },
    { "id": 15, "tasks": ["12.1"] }
  ]
}
```
