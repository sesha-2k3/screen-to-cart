# Design: Phase 2 Identify

## Overview

Phase 2 implements build plan section 6, Phase 2 steps 1–5 and 7, using the free-tier rules in section 2. This document records only the decisions the plan doesn't make. The biggest one is where eval inputs come from (Eval below): the backend can't fetch YouTube frames or transcripts, so the eval set is built from real captures made with the extension.

Models were checked on the Groq docs on November 7, 2026: `qwen/qwen3.8-27b` is still the vision model, with JSON mode, 3 images per request and 2,048 tokens per image. At `reasoning_effort` default it returns no reasoning tokens, which is the plan's "instruct mode", so no extra parameter is set.

## Architecture

```
POST /identify
  → select_sharpest (Phase 1)            → SSE frame_selected
  → graph.astream(stream_mode="updates")
      START → identify (Tier 1)          → SSE candidates {tier: 1}
            → needs_tier2? ──yes──→ disambiguate (Tier 2) → SSE candidates {tier: 2}
                           ──no───→ END
  → write identify cache (video_id, floor(t / 5))
```

| File | Contents |
|---|---|
| `app/schemas.py` | `Evidence`, `ProductCandidate`, `Candidates`, `CandidatesEvent`, `ErrorEvent`, `LookupResult` |
| `app/graph/state.py` | `PipelineState` |
| `app/graph/prompts.py` | `PROMPT_VERSION`, Tier 1 and Tier 2 prompt builders, `trim_description` |
| `app/graph/nodes/identify.py`, `disambiguate.py` | One node each |
| `app/graph/build.py` | `build_graph()` and the `needs_tier2` edge |
| `app/llm/invoke.py` | `invoke_json(role, messages, schema, config)`: rate limit, record/replay, call, validate, retry once |
| `app/llm/rate_limit.py` | Per-model token bucket |
| `app/llm/fixtures.py` | Record/replay storage |
| `app/db/models.py`, `session.py`, `identify_cache.py` | ORM model, async engine, get/put |
| `eval/run.py`, `eval/metrics.py` | Runner and exact-match scoring |

The graph is retrieve-ready: Phase 3 adds the retailer fan-out after `needs_tier2`'s two branches meet.

## Components and Interfaces

### LLM calls: `invoke_json`

Both LLM nodes need the same steps, so they share one helper instead of each wrapping the model:

1. Estimate tokens: 2,048 per image + characters / 4 for text + 1,024 for output. Wait for the model's bucket.
2. Look up the stored response if `LLM_MODE` is `record` or `replay`.
3. Otherwise call `get_llm(role).ainvoke(messages, config)`, passing the request's Langfuse callbacks through `config`.
4. Validate `response.content` with `schema.model_validate_json`. On a `ValidationError`, call once more; a second failure raises `LlmOutputError`.
5. In `record` mode, store the raw response text.

JSON mode is turned on in the Groq builder in `factory.py` (`response_format={"type": "json_object"}`), because every role in the plan returns JSON. Prompts carry the JSON shape in plain text, so they also work on Anthropic later (plan section 7).

### Rate limiter

`langchain_core`'s `InMemoryRateLimiter` counts requests, but the binding free-tier limit is 8K tokens per minute, so the limiter is a small token bucket per model spec (capacity and refill from `GROQ_TPM_LIMIT`, default 8,000).

- The Groq builder gives `ChatGroq` its own `httpx.AsyncClient` with a response hook. `ChatGroq` doesn't expose response headers, and the hook is the only place to read them. The hook sets the bucket to `x-ratelimit-remaining-tokens`.
- `ChatGroq(max_retries=0)`. The Groq SDK otherwise retries 429s for up to 60 s per attempt, and the user would see a frozen panel. On `groq.RateLimitError`, `invoke_json` raises `RateLimited(retry_after_seconds)` from the `retry-after` header.
- If the bucket would wait more than 20 s, `RateLimited` is raised right away with that wait, for the same reason.
- The eval runner catches `RateLimited`, sleeps `retry_after_seconds` and retries the item.

### Record/replay

- Key: SHA-256 of the model spec plus the JSON-serialized messages. The image is part of the hashed input, so a different frame or prompt is a different key. Prompt version and model are covered by the key, which is the plan's eval cache key `(item, prompt_version, model)` in practice.
- File: `fixtures/llm/<key>.json` with `role`, `model`, `prompt_version` and `content` (the response text). The image is never written.
- `record` reads before calling, so re-running an unchanged eval costs no tokens. `replay` raises `FixtureMissing` (naming the key and role) on a miss.

### Prompts

`PROMPT_VERSION = "identify-v1"` lives in `prompts.py` and changes whenever a prompt changes. Plan step 6 (Langfuse prompt management) is skipped: it adds a network call per request, and the record/replay key already ties results to the exact prompt text.

- Tier 1: system instructions plus a user message with the image (`data:image/jpeg;base64,…`), title, trimmed description and transcript. It asks for up to 3 candidates sorted by confidence, each with evidence and 1–3 search queries.
- Tier 2: text only. Tier 1's candidates (including `visual_notes`) plus the same text context. It returns the same `Candidates` shape, best first.
- `trim_description`: lines containing `http` or a word with both letters and digits (model numbers like `WH-1000XM5`) first, then the rest in order, cut at 1,500 characters.

### Tier 2 rule

`needs_tier2(state)` is true when the top candidate's confidence is below `TIER2_CONFIDENCE_THRESHOLD` (default 0.7) or there is more than one candidate. With no candidates it is false and the stream ends with an empty `candidates` event. Phase 6 tunes the threshold.

### Identify cache

Table `identify_cache`: `video_id` (text), `bucket` (int, `floor(t / 5)`), `result` (JSONB, a `Candidates`), `created_at`. Primary key `(video_id, bucket)`; a write for an existing key replaces it. Migration `0002`; `env.py` points at `Base.metadata`.

- `/lookup` and `/identify` get an `IdentifyCache` through a FastAPI dependency, so tests swap in an in-memory one.
- Database errors are logged and treated as a miss (lookup) or skipped (write). The extension must never fail because Postgres isn't running.
- Only the final candidates are cached. A stream that ended in an error isn't cached.

### Eval

The backend can't get frames or transcripts for a `video_id` on its own (Phase 1 design: YouTube blocks direct caption fetches, and the plan keeps capture in the browser). So eval items are real captures:

1. The user sets `SAVE_EVAL_CAPTURES=true` and `LLM_MODE=record` and captures moments with the extension. `/identify` writes `backend/eval/captures/<video_id>_<t>.json`: the request with only the sharpest frame. The folder is gitignored, because it holds video frames.
2. Because of `record`, these captures also store the Tier 1 (and Tier 2) responses, so the eval run that follows costs no tokens.
3. `uv run python -m eval.stub_labels` appends a label line for each capture not yet in `labels.jsonl`, with `video_id` and `timestamp` filled in. The user fills in `brand`, `model`, `product_url`, `category` and `is_short`.
4. `uv run python -m eval.run --subset dev` runs the graph on the first 50 labeled items in `record` mode and writes `backend/eval/reports/<date>-identify.md`.

Fifty captures cost about 50 vision calls, which is about one day of the vision model's 200K tokens. Spread capturing over two sessions if a 429 appears.

Scoring (`eval/metrics.py`): normalize by lowercasing and removing everything except letters and digits. A candidate is correct when the normalized label brand is in the normalized candidate brand, and the normalized label model is in the normalized candidate `brand + model`. Tier 1 accuracy uses Tier 1's top candidate; Tier 1+2 uses the final top candidate.

### Side panel

- `lib/api.ts` handles `candidates` and `error` events.
- A `CandidateList` component shows the top candidate (brand, model, category, confidence) and the others as chips. Clicking a chip does nothing yet; Phase 3 searches it.
- On a cache hit, the background stores the `/lookup` result in the `cached` state, and the panel shows it with the same component.
- `rate_limited` shows "Rate limited. Try again in N seconds."

## Data Models

| Model | Fields |
|---|---|
| `Evidence` | `source` (`visual`, `transcript`, `description`), `detail` |
| `ProductCandidate` | `brand`, `model`, `category`, `color` (nullable), `confidence` (0–1), `evidence`, `search_queries`, `visual_notes` |
| `Candidates` | `candidates` (best first). The LLM output schema for both tiers, and the cached result |
| `CandidatesEvent` | `tier` (1 or 2), `candidates` |
| `ErrorEvent` | `code` (`rate_limited`, `upstream_error`), `message`, `retry_after_seconds` (nullable) |
| `LookupResult` | `video_id`, `bucket`, `candidates` |

`PipelineState` (TypedDict): `video_id`, `frame` (base64), `title`, `description`, `transcript`, `candidates`, `tier`.

New settings: `TIER2_CONFIDENCE_THRESHOLD` (default 0.7), `GROQ_TPM_LIMIT` (default 8000), `SAVE_EVAL_CAPTURES` (default false).

## Correctness Properties

- Each vision call carries exactly one image.
- Tier 2 runs if and only if the Tier 2 rule holds.
- Invalid JSON is retried once, never more.
- A 429 becomes a `rate_limited` event with the server's `retry-after`; no silent retries.
- `replay` never makes a network call; `record` makes one only when no stored response exists.
- Stored fixtures and the identify cache contain no image data.
- A database failure never fails `/lookup` or `/identify`.

## Error Handling

| Situation | What the user sees |
|---|---|
| 429 or a bucket wait over 20 s | `error` event `rate_limited`; panel: "Rate limited. Try again in N seconds." |
| Invalid JSON twice | `error` event `upstream_error`; panel: "Couldn't identify the product. Try again." |
| Other Groq API error | `upstream_error`, as above |
| No candidates | Empty `candidates` event; panel: "No product found in this frame." |
| Postgres down | Nothing; the cache is skipped and a warning is logged |
| `replay` miss | `upstream_error` naming the missing fixture (only in dev) |

## Testing Strategy

No test calls Groq. Node tests use LangChain's `FakeListChatModel` through a patched `get_llm`, with canned JSON strings.

- Identify node: valid JSON becomes candidates and the request has exactly one image; invalid then valid JSON retries once; invalid twice raises `LlmOutputError`.
- Tier 2 rule: high confidence with one candidate skips Tier 2; low confidence or two candidates runs it.
- Rate limiter: a bucket with too few tokens raises `RateLimited` with the wait; the header hook sets the remaining tokens.
- Record/replay: `record` stores once and the second call doesn't hit the model; `replay` raises on a miss; the stored file has no image.
- `trim_description`: link and model-number lines are kept first, total ≤ 1,500.
- Endpoints: `/identify` streams `frame_selected` then `candidates` and writes the cache; `/lookup` returns the cached result and 404 on a miss; a failing cache doesn't fail either endpoint.
- Eval scoring: a few matching and non-matching brand/model pairs.
