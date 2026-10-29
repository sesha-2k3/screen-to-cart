---
inclusion: always
---

# Tech stack and hard rules

## Stack
- Extension: WXT + React + TypeScript (Manifest V3), side panel via `chrome.sidePanel`. Package manager: pnpm.
- Backend: Python 3.12, FastAPI, Pydantic, `sse-starlette` for streaming. Package manager: **uv**.
- Orchestration: LangGraph (`StateGraph`, `Send` fan-out, conditional edges, `astream(stream_mode="updates")`).
- LLMs (free tier, Groq via `langchain-groq`):
  - identify (vision): `qwen/qwen3.8-27b`
  - disambiguate (text): `openai/gpt-oss-120b`
  - verify / refine / sponsorship: `openai/gpt-oss-20b`
- Embeddings: SigLIP (`google/siglip-base-patch16-224`) on CPU via `transformers` + CPU-only `torch`.
- Database: Postgres 16 + pgvector, SQLAlchemy async + asyncpg, Alembic migrations.
- Retailers: eBay Browse API, Best Buy API, via `httpx` async.
- Tracing and evals: Langfuse (Cloud, Hobby plan).

## Hard rules
- Python dependencies: always `uv add <pkg>` (or `uv add --dev`, `uv add --group eval`). Never `pip install`, never edit dependency lists by hand. Run things with `uv run ...`.
- Extension dependencies: `pnpm add` / `pnpm add -D`.
- Never hard-code model names. Every node gets its model from `get_llm(role)` in `backend/app/llm/`, which reads env config. Switching to Anthropic later must be a config change.
- Never hard-code secrets. Read them via `pydantic-settings` from `.env`. Only `.env.example` (no values) is committed.
- **The user edits `.env` by hand. Never read, write, copy or source `.env` (hooks will block it).** When a new setting is needed: add the variable name with no value to `.env.example`, add the field to `app/config.py`, and tell the user which variable to set in their `.env`. To see which variables exist, read `.env.example` or `app/config.py`.
- Pydantic models in `backend/app/schemas.py` are the single source of truth for API payloads and LLM structured output. The extension's types are generated from FastAPI's OpenAPI schema with `openapi-typescript`; never hand-write duplicate TS types for API payloads.
- Async everywhere on the backend I/O path (FastAPI handlers, retailer adapters, DB).
- Each request creates its own Langfuse `CallbackHandler`; non-LangChain code (frame selection, retailer adapters, SigLIP) is wrapped with `@observe()`.
