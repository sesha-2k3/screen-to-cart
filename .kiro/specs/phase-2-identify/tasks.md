# Implementation Plan: Phase 2 Identify

## Overview

Build plan Phase 2 steps 1–5 and 7. See `requirements.md` for scope and `design.md` for the decisions. Each task stays under about 200 lines of new code.

## Tasks

- [ ] 1. Schemas and settings
  - `Evidence`, `ProductCandidate`, `Candidates`, `CandidatesEvent`, `ErrorEvent`, `LookupResult` in `schemas.py`
  - Settings `tier2_confidence_threshold`, `groq_tpm_limit`, `save_eval_captures`; names added to `.env.example`
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 2. Rate limiter
  - `app/llm/rate_limit.py`: token bucket per model spec, `acquire(tokens)` raises `RateLimited` when the wait would exceed 20 s, `observe(response)` hook reads `x-ratelimit-remaining-tokens`
  - Groq builder: its own `httpx.AsyncClient` with the hook, `max_retries=0`, JSON mode
  - Tests: too few tokens raises with the wait; the hook sets the remaining tokens
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 3. Record/replay and `invoke_json`
  - `app/llm/fixtures.py`: key, read, write (no image in the file) under `fixtures/llm/`
  - `app/llm/invoke.py`: estimate → acquire → fixture lookup → `ainvoke` → validate → retry once → store; `groq.RateLimitError` → `RateLimited` with `retry-after`
  - Tests: invalid then valid JSON retries once; invalid twice raises; `record` calls the model once for two identical requests; `replay` raises on a miss
  - _Requirements: 2.2, 2.3, 3.4, 5.4, 6.1, 6.2, 6.3, 6.4_

- [ ] 4. Prompts and trimming
  - `app/graph/prompts.py`: `PROMPT_VERSION`, Tier 1 messages (one image + text context), Tier 2 messages (text only), `trim_description`
  - Test: `trim_description` keeps link and model-number lines first and stays ≤ 1,500 characters
  - _Requirements: 2.1, 3.3, 4.1, 4.2, 4.3_

- [ ] 5. Graph: identify, disambiguate, Tier 2 rule
  - `graph/state.py`, `graph/nodes/identify.py`, `graph/nodes/disambiguate.py`, `graph/build.py` with `needs_tier2`
  - Tests: each node called directly with a hand-built state and a fake model (Tier 1 request has exactly one image); `needs_tier2` for confident/single, low-confidence and two-candidate cases
  - _Requirements: 2.1, 3.1, 3.2, 3.3_

- [ ] 6. Identify cache in Postgres
  - `db/models.py`, `db/session.py`, `db/identify_cache.py` (`get`, `put`, errors logged and treated as a miss); migration `0002_identify_cache`; `env.py` uses `Base.metadata`
  - The user runs `uv run alembic upgrade head` against the Docker database
  - _Requirements: 7.1, 7.2, 7.3_

- [ ] 7. Endpoints
  - `/identify`: after `frame_selected`, run `graph.astream(stream_mode="updates")` with a new `CallbackHandler` inside `trace_attributes`; send `candidates` per node, `error` on `RateLimited` / `LlmOutputError` / Groq API errors; write the cache at the end
  - `/lookup`: `LookupResult` on a hit, 404 on a miss
  - `SAVE_EVAL_CAPTURES`: write the request with only the sharpest frame to `backend/eval/captures/`; gitignore the folder
  - List the new event models in `responses`; regenerate `extension/lib/api-types.ts`
  - Tests (in-memory cache, fake model): stream order and cache write; lookup hit and miss; a failing cache doesn't fail either endpoint
  - _Requirements: 2.4, 7.1, 7.2, 7.3, 8.1, 8.2, 9.1, 9.2_

- [ ] 8. Side panel
  - `lib/api.ts` handles `candidates` and `error`; `CandidateList` component (top candidate + chips); background puts the `/lookup` result in the `cached` state
  - Messages for `rate_limited`, `upstream_error` and no candidates (design, Error Handling)
  - _Requirements: 8.3, 8.4_

- [ ] 9. Checkpoint: automated checks
  - `uv run pytest -q`, `uv run ruff check .`, `uv run mypy app` in `backend/`; `pnpm compile`, `pnpm test` and `pnpm build` in `extension/`

- [ ] 10. Eval runner
  - `eval/stub_labels.py`: append a label line for each capture not in `labels.jsonl`
  - `eval/metrics.py`: normalize and exact-match (design, Eval); `eval/run.py --subset dev`: run the graph per item in `record` mode, sleep and retry on `RateLimited`, write the report with Tier 1 accuracy, Tier 1+2 accuracy and Tier 2 call rate
  - Test: scoring on a few matching and non-matching pairs
  - _Requirements: 10.1, 10.2_

- [ ] 11. Live check in Chrome (the user runs this)
  - Set `LLM_MODE=record`, `SAVE_EVAL_CAPTURES=true` and a real `GROQ_API_KEY`; capture a few videos and confirm candidates appear, a second trigger in the same 5 s window is a cache hit, and a trace shows Tier 1 (and Tier 2 when it runs) in Langfuse
  - _Requirements: 2.1, 3.1, 7.2, 8.3_

- [ ] 12. Final checkpoint: Phase 2 "Done when" (the user labels; the agent runs the dev eval)
  - The user captures 50 moments (spread over two days if the vision quota runs out) and fills in `labels.jsonl` from the stubs
  - Run `uv run python -m eval.run --subset dev`; record Tier 1 and Tier 1+2 accuracy and the Tier 2 call rate here
  - _Requirements: 9.3, 10.1, 10.2_

## Notes

- Tests never call Groq or Postgres. LLM nodes use `FakeListChatModel` through a patched `get_llm`; the cache uses an in-memory stand-in through the FastAPI dependency.
- Tasks 11 and 12 use live quota. The agent doesn't start them; the user does.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "2"] },
    { "id": 1, "tasks": ["3", "4", "6"] },
    { "id": 2, "tasks": ["5"] },
    { "id": 3, "tasks": ["7"] },
    { "id": 4, "tasks": ["8", "10"] }
  ]
}
```
