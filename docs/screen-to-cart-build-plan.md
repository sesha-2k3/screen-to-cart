# Screen to Cart — Build Plan

> **Screen to Cart:** find anything you see in a video, compared across stores.

Screen to Cart is a Chrome extension that identifies products in a YouTube video or Short at the moment the user asks, then finds them across retailers with a price comparison, a sponsorship flag, and the evidence behind each match.

This plan starts on **free-tier models (Groq)** and is built so that switching to paid models later is a config change, not a rewrite.

---

## 1. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Extension | WXT + React + TypeScript (Manifest V3) | Side panel UI via `chrome.sidePanel` |
| Backend | Python 3.12 + FastAPI | Async, Pydantic, SSE streaming |
| Orchestration | LangGraph | Fan-out retrieval, verify/refine loop |
| LLM provider (now) | Groq free tier via `langchain-groq` | See section 2 |
| LLM provider (later) | Anthropic (Claude Haiku / Sonnet) | Same interface, swap in config |
| Embeddings | SigLIP (`google/siglip-base-patch16-224`) | Runs locally on CPU, free |
| Image processing | OpenCV, Pillow | Sharpest-frame selection, cropping |
| Matching | `rapidfuzz` | Fuzzy title dedupe |
| Database | Postgres 16 + pgvector | Products, listings, cache, eval labels, embeddings |
| Retailer data | eBay Browse API, Best Buy API | Both free |
| Tracing & evals | Langfuse Cloud (free Hobby plan) | 50k units/month (traces + observations + scores), 30-day data access, 2 users |
| Local infra | Docker Compose | Postgres + backend |

---

## 2. Model plan (free tier)

Groq's vision support changes often, so confirm these on the Groq docs before you start. As of **October 25, 2026**:

| Role | Model | Why |
|---|---|---|
| Tier 1 — vision identify | `qwen/qwen3.8-27b` (instruct mode) | Groq's free vision model; supports JSON mode and tool use |
| Tier 2 — disambiguation | `openai/gpt-oss-120b` | Text-only reasoner; works from Tier 1's visual description + transcript + description |
| Verify / refine / sponsorship | `openai/gpt-oss-20b` | Small, fast, cheap on tokens |

Tier 2 is text-only on purpose. Tier 1 writes a detailed visual description (brand text, logos, colors, shape), and Tier 2 reasons over that together with the transcript and video description. This gets you a "stronger second opinion" without a second vision call, and it uses a separate rate-limit bucket.

Vision model constraints to design around:

- Max **3 images per request**.
- Each image counts as **2,048 input tokens**, regardless of size.
- So: pick the sharpest frame locally and send **one** image, not three.

### Free-tier rate limits (the real constraint)

Free-plan base limits shown on Groq's rate-limits page (check your own limits at `console.groq.com/settings/limits`, since they vary by account):

| Model | RPM | RPD | TPM | TPD |
|---|---|---|---|---|
| `qwen/qwen3.8-27b` | 30 | 1K | 8K | 200K |
| `openai/gpt-oss-120b` | 30 | 1K | 8K | 200K |
| `openai/gpt-oss-20b` | 30 | 1K | 8K | 200K |

What this means per identify call (~2,048 image + ~1,600 text input + ~400 output ≈ **4K tokens**):

- **About 2 identify calls per minute** (8K TPM is the binding limit).
- **About 50 identify calls per day** (200K TPD).

This shapes the whole build:

1. **Cache everything.** Key identify results by `video_id + 5s timestamp bucket`. Key eval results by `(eval_item_id, prompt_version, model)` so re-running an unchanged config costs nothing.
2. **Record/replay mode for UI work.** Save real API responses as fixtures and serve them when `LLM_MODE=replay`. Build the extension and side panel against fixtures so you don't burn quota on CSS changes.
3. **Trim inputs.** Cap the description at ~1,500 characters (keep lines containing links and product names first) and the transcript window at ±30s.
4. **Respect the headers.** Read `x-ratelimit-remaining-tokens` and back off on `429` using `retry-after`.
5. **Use a 50-item dev subset** for day-to-day evaluation, and run the full 200-item set only at milestones (spread over a few days).

---

## 3. Architecture

```
Trigger: hotkey (works without opening anything) / "What's this?" in the side panel
      ↓
Pause video at time t (content script)
      ↓
Quick cache check: GET /lookup?video_id&t ──hit──→ show cached result, done
      ↓ miss
Capture (content script + service worker)
  frames: t, t−0.5s, t−1.0s (seek back within the buffered video, captures ≥0.5s apart)
  YouTube controls hidden during capture · crop to the video rect
  + transcript ±30s · title · description · paid-promo label
      ↓
POST /identify (frames + context) ── SSE stream opens back to the side panel
      ↓
Frame selector (OpenCV: sharpest of the 3 by Laplacian variance)
      ↓
┌───────────────────── LANGGRAPH PIPELINE ─────────────────────┐
│ Sponsorship check (runs in PARALLEL from the start:          │
│   promo label, transcript phrases, affiliate links)          │
│                                                              │
│ Tier 1: qwen3.8-27b (vision) → candidates + visual notes     │
│         + confidence                                         │
│      ↓ (only if low confidence / several items)              │
│ Tier 2: gpt-oss-120b (text) → exact brand + model            │
│      ↓                                                       │
│ Retrieve (the search): eBay | Best Buy, parallel via Send    │
│   for the top candidate only; others searched on click       │
│      ↓                                                       │
│ Resolve: dedupe (GTIN / fuzzy) → SigLIP rerank               │
│          → price breakdown → attach sponsorship result       │
│      ↓                                                       │
│ Verify: good match? ──no──→ refine query (gpt-oss-20b, ≤2×)  │
└──────────────────────────────────────────────────────────────┘
      ↓ (every node's update streamed live over SSE, not just at the end)
Side panel (React)
  live status · candidate chips · product card · price breakdown
  · sponsored flag · "why this match"
      ↓
Result cached (video_id + 5s bucket) · user clicks a listing → retailer page opens in a new tab
      ↕
Storage: Postgres (products, listings, cache, eval labels) + pgvector (SigLIP embeddings)
```

Latency targets: product name in **≤ 2s**, full listings in **≤ 6s** (cache misses).

### End-to-end request flow

1. **Trigger.** The user presses the hotkey (registered with `chrome.commands`) or clicks "What's this?" in the side panel. Opening the side panel on its own does nothing; the button press is the trigger. The hotkey also opens the side panel if it's closed.
2. **Freeze the moment.** The content script records the current time `t` and pauses the video, so the product stays on screen while the user waits and the capture is of exactly the moment they meant.
3. **Cache check first.** The extension sends `video_id` + `t` to a cheap `GET /lookup`. On a hit (someone already asked about this 5-second window) the result comes back instantly, nothing is captured or uploaded, and no model quota is used.
4. **Capture frames.** On a miss, the content script hides YouTube's overlay controls (progress bar, Shorts buttons) and the service worker calls `chrome.tabs.captureVisibleTab`. The extension then seeks back 0.5s and 1.0s (the video is already buffered there, so seeks are fast) and captures again. Two corrections to the earlier plan:
   - A screenshot can only capture what's on screen *now*, so "t−1s" has to come from seeking back, not from the past.
   - Chrome limits `captureVisibleTab` to about 2 calls per second, so captures must be at least 0.5s apart. Three frames take about 1 second.
   After capture, the extension restores the controls and `currentTime = t`, and leaves the video paused.
5. **Crop.** The service worker crops each screenshot to the video element's rectangle (scaled by `devicePixelRatio`) using `OffscreenCanvas`, and encodes it as JPEG. Only the crops leave the browser.
6. **Gather context.** The content script reads the transcript ±30s around `t` (fetched in the browser from the page's caption track), the title, the description, and whether the "Includes paid promotion" label is shown.
7. **Send and stream.** The extension POSTs frames + context to `/identify`. The response is an SSE stream, so the side panel starts showing progress immediately.
8. **Pick the frame.** The backend scores the three crops by Laplacian variance and keeps the sharpest. Only that one goes to the vision model (each image costs 2,048 tokens on Groq).
9. **Run the LangGraph pipeline.**
   - **Sponsorship check** starts in parallel right away, because it only needs the promo label, transcript and description, not the identified product.
   - **Tier 1** (vision) returns product candidates, visual notes and confidence.
   - **Tier 2** (text) runs only if Tier 1 is unsure or found several items.
   - **Retrieve** is the search step: the eBay and Best Buy adapters run in parallel. When there are several candidates, search only the top one automatically and show the rest as chips the user can click to search, which keeps free-tier quota for what the user actually wants.
   - **Resolve** dedupes listings, reranks them with SigLIP, builds the price breakdown, and attaches the sponsorship result.
   - **Verify** checks match quality and loops through **refine** (at most twice) if results are weak.
10. **Show results.** The side panel fills in as each node finishes: the product name first, then listings, price breakdown, sponsored flag and "why this match".
11. **Cache and act.** The final result is cached under `video_id` + 5-second bucket. Clicking a listing opens the retailer's page in a new tab. The user resumes the video when they're ready.

### Permissions

| Permission | Why |
|---|---|
| `activeTab` | Lets `captureVisibleTab` screenshot the current tab when the user presses the hotkey or clicks the toolbar icon |
| `sidePanel` | The results UI |
| `scripting` | Inject the content script if needed |
| host permission for `https://www.youtube.com/*` | Content script on YouTube pages |

`activeTab` is only granted by certain user gestures (the hotkey, clicking the toolbar icon) and ends when the tab navigates. Test early whether a click on the side panel's "What's this?" button, after moving to a new video, still allows capture. If it doesn't, either have the button tell the user to use the hotkey, or request the broader `<all_urls>` permission, which shows a bigger install warning.

---

## 4. Repository layout

```
screen-to-cart/
├── extension/                 # WXT + React + TS
│   ├── entrypoints/
│   │   ├── content.ts         # reads video, time, transcript, description, promo label
│   │   ├── background.ts      # captureVisibleTab, hotkey, messaging
│   │   └── sidepanel/         # React app
│   ├── lib/api.ts             # typed client (openapi-fetch + generated types)
│   ├── lib/api-types.ts       # generated by openapi-typescript
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, /lookup (cache), /identify (SSE), /health
│   │   ├── config.py          # provider + model names per node (env-driven)
│   │   ├── observability.py   # Langfuse client, per-request CallbackHandler, @observe helpers
│   │   ├── llm/               # provider factory, rate limiter, record/replay
│   │   ├── graph/             # state.py, nodes/, build.py
│   │   ├── retailers/         # base.py, ebay.py, bestbuy.py
│   │   ├── vision/            # frame_select.py, siglip.py
│   │   ├── db/                # models, migrations (Alembic), pgvector
│   │   └── schemas.py         # Pydantic models (shared with LLM structured output)
│   ├── eval/                  # labeled set, runner, metrics, reports
│   ├── tests/
│   ├── pyproject.toml         # uv project: dependencies, groups, torch CPU index
│   ├── uv.lock                # committed lockfile
│   ├── .python-version        # 3.12
│   └── Dockerfile             # uv sync --frozen --no-dev
├── fixtures/                  # recorded LLM + retailer responses
├── .env.example
└── docker-compose.yml         # postgres+pgvector, backend
```

### Naming conventions

| Where | Name |
|---|---|
| Product name (titles, store listing, manifest `name`) | Screen to Cart |
| Tagline (manifest `description`, store listing) | Find anything you see in a video, compared across stores. |
| Repo and folders | `screen-to-cart` |
| Python project (`pyproject.toml`) | `screen-to-cart-backend` |
| Extension package (`package.json`) | `screen-to-cart-extension` |
| Database | `screen_to_cart` |
| Docker Compose project | `screen-to-cart` (set `name:` at the top of `docker-compose.yml`) |
| Langfuse project | Screen to Cart |

In the extension, set the display name in `wxt.config.ts` (`manifest.name = "Screen to Cart"`) and set `"name": "screen-to-cart-extension"` in `package.json` after running `wxt init`.

---

## 5. Dependencies and setup

### Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Python | 3.12 (managed by uv) | Backend. Langfuse's LangGraph integration needs 3.11+ |
| uv | latest | Python package and environment manager |
| Node.js | current LTS | Extension build (WXT) |
| pnpm or npm | latest | Extension packages |
| Docker + Docker Compose | latest | Postgres + pgvector locally |

Don't pin versions in this document. Let `uv lock` and the npm lockfile resolve them, and commit both lockfiles (`uv.lock`, `pnpm-lock.yaml` / `package-lock.json`) so every machine installs the same versions.

### Backend (Python, with uv)

Create the project:

```bash
cd screen-to-cart
uv init backend --app --python 3.12 --name screen-to-cart-backend
cd backend
```

Core runtime dependencies:

```bash
# API server and streaming
uv add fastapi "uvicorn[standard]" sse-starlette pydantic pydantic-settings

# Orchestration and LLM providers
uv add langgraph langchain-core langchain-groq

# Tracing, evals, prompt management
uv add langfuse

# HTTP client for retailer APIs
uv add httpx

# Database
uv add "sqlalchemy[asyncio]" asyncpg alembic pgvector

# Vision and embeddings
uv add opencv-python-headless pillow numpy torch transformers sentencepiece

# Matching
uv add rapidfuzz
```

What each one is for:

| Package | Purpose |
|---|---|
| `fastapi` | API framework |
| `uvicorn[standard]` | ASGI server (the `standard` extra adds faster event loop and HTTP parsing) |
| `sse-starlette` | Server-sent events for streaming graph updates to the side panel |
| `pydantic` | Schemas for API payloads and LLM structured output |
| `pydantic-settings` | Typed config from `.env` (model names per node, API keys) |
| `langgraph` | The pipeline graph: nodes, `Send` fan-out, conditional edges, streaming |
| `langchain-core` | Message types and chat model interface used by LangGraph |
| `langchain-groq` | Groq chat models (`ChatGroq`), including vision via image messages |
| `langfuse` | Tracing (`CallbackHandler`, `@observe()`), datasets, scores, prompt management |
| `httpx` | Async HTTP client for the eBay and Best Buy adapters |
| `sqlalchemy[asyncio]` | ORM / query layer with async support |
| `asyncpg` | Async Postgres driver |
| `alembic` | Database migrations |
| `pgvector` | pgvector column type and distance operators for SQLAlchemy |
| `opencv-python-headless` | Sharpest-frame selection (Laplacian variance), cropping. Headless = no GUI libs, smaller in Docker |
| `pillow` | Image decoding/encoding (base64 frames in and out) |
| `numpy` | Array math for images and embeddings |
| `torch` | Runtime for SigLIP (CPU build, see below) |
| `transformers` | Loads SigLIP (`AutoModel`, `AutoProcessor`) |
| `sentencepiece` | Tokenizer needed by SigLIP's text encoder |
| `rapidfuzz` | Fuzzy title matching for listing dedupe |

#### CPU-only PyTorch

The default `torch` wheel on Linux includes CUDA and is several GB. You don't need a GPU for SigLIP base, so point uv at the CPU index. Add this to `backend/pyproject.toml` **before** running `uv add torch` (or run `uv lock` again after adding it):

```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = [{ index = "pytorch-cpu", marker = "sys_platform != 'darwin'" }]
```

On macOS the regular PyPI wheel is already CPU-only, which is why the marker skips it there.

#### Development tools

```bash
uv add --dev pytest pytest-asyncio respx ruff mypy
```

| Package | Purpose |
|---|---|
| `pytest`, `pytest-asyncio` | Tests, including async nodes and endpoints |
| `respx` | Mock `httpx` calls so retailer adapter tests don't hit real APIs |
| `ruff` | Linting and formatting |
| `mypy` | Type checking |

#### Evaluation tools (separate group)

```bash
uv add --group eval pandas matplotlib
```

`pandas` builds the results tables (accuracy, latency, cost per config) and `matplotlib` draws the ablation and threshold charts. Keeping them in their own group means the production image doesn't install them.

#### Later, when moving to paid models

```bash
uv add langchain-anthropic
```

#### Everyday uv commands

```bash
uv sync                                 # install everything from uv.lock (incl. dev group)
uv sync --group eval                    # also install the eval group
uv run uvicorn app.main:app --reload    # run the API
uv run alembic upgrade head             # apply migrations
uv run pytest                           # run tests
uv run ruff check . && uv run ruff format .
uv run python -m eval.run --subset dev  # run the 50-item dev eval
uv lock --upgrade                       # upgrade dependencies deliberately
```

In the backend `Dockerfile`, install with `uv sync --frozen --no-dev` so the image uses exactly what's in `uv.lock` and skips dev and eval tools.

### Extension (TypeScript)

Scaffold with WXT's React template, then add the rest:

```bash
cd screen-to-cart
pnpm dlx wxt@latest init extension   # choose the React template
cd extension
pnpm add @microsoft/fetch-event-source openapi-fetch
pnpm add -D openapi-typescript
```

| Package | Purpose |
|---|---|
| `wxt` | Extension framework: Manifest V3 build, hot reload, entrypoints (comes with the template) |
| `@wxt-dev/module-react` | React support in WXT (comes with the React template) |
| `react`, `react-dom` | Side panel UI (comes with the template) |
| `typescript`, `@types/react`, `@types/react-dom` | Types (comes with the template) |
| `@microsoft/fetch-event-source` | SSE over POST. The browser's built-in `EventSource` only supports GET, and `/identify` needs to POST the frame and transcript |
| `openapi-fetch` | Small typed `fetch` wrapper for the non-streaming endpoints |
| `openapi-typescript` (dev) | Generates TypeScript types from FastAPI's `/openapi.json` |

Generate the API types whenever the backend schema changes:

```bash
pnpm openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts
```

Styling is your choice; Tailwind works with WXT if you want it, but nothing in the plan depends on it.

### Local infrastructure

`docker-compose.yml` needs one service to start: the `pgvector/pgvector:pg16` image. After the database starts, enable the extension once (put this in your first Alembic migration):

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Environment variables (`.env.example`)

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/screen_to_cart

# LLM provider (free tier)
GROQ_API_KEY=
IDENTIFY_VISION_MODEL=groq:qwen/qwen3.8-27b
DISAMBIGUATE_MODEL=groq:openai/gpt-oss-120b
REFINE_MODEL=groq:openai/gpt-oss-20b
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
```

---

## 6. Build phases

Roughly 8–10 weeks solo. Every phase ends with something you can demo.

### Phase 0 — Setup (2–3 days)

1. Create the repo with the layout above. Set up the backend with `uv init backend --app --python 3.12 --name screen-to-cart-backend`, add the CPU-only torch index to `pyproject.toml`, then add the packages from section 5.
2. `docker-compose.yml` with `pgvector/pgvector:pg16` and the backend service.
3. Accounts and keys: Groq, eBay Developer Program, Best Buy Developer, Langfuse Cloud. Put them in `.env` (and `.env.example` without values), including `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL`.
4. Backend skeleton: FastAPI with `/health`, Alembic migrations, `config.py` reading model names per node from env.
5. **Provider factory** in `app/llm/`: one function `get_llm(role)` that returns a LangChain chat model for `identify_vision`, `disambiguate`, `refine`, `sponsorship`. Groq now, Anthropic later.
6. Extension skeleton with WXT's React template (section 5): side panel opens and pings `/health`.
7. Langfuse tracing (`uv add langfuse`), set up in `app/observability.py`:
   - Create a new `CallbackHandler` **per request** (don't share one across concurrent requests) and pass it as `config={"callbacks": [handler]}` to `graph.astream(...)`.
   - Wrap each run in `propagate_attributes(trace_name="identify", session_id=video_id, tags=[provider])` so traces have useful names and can be filtered by provider (`groq-free` now, `anthropic` later).
   - Decorate non-LangChain code with `@observe()` (frame selection, retailer adapters, SigLIP rerank) so it appears as spans in the same trace.

**Done when:** `docker compose up` brings up DB + API, the side panel shows "backend OK", and a test request shows up as a named trace in Langfuse.

### Phase 1 — Capture (week 1–2)

1. Content script: detect video ID (regular and Shorts URLs), current time, video element bounding box, title, description, and the "Includes paid promotion" label.
2. Transcript: read caption tracks from the page's player data and fetch the track from the browser; slice ±30s around the timestamp.
3. Trigger and capture, following the request flow in section 3:
   - Hotkey via `chrome.commands` and the side panel's "What's this?" button.
   - Pause the video at `t`, call `GET /lookup` for a cache hit, and capture only on a miss.
   - Hide YouTube's overlay controls, then capture frames at `t`, `t−0.5s` and `t−1.0s` by seeking back, at least 0.5s apart (Chrome's capture rate limit).
   - Restore controls and `currentTime = t`; leave the video paused.
   - Crop each frame to the video rect with `OffscreenCanvas`, accounting for `devicePixelRatio`, and encode as JPEG.
4. Backend `frame_select.py`: pick the sharpest of the three frames by Laplacian variance.
5. Side panel shows the chosen crop, transcript snippet, and description raw.

**Done when:** it works on 10 regular videos and 10 Shorts, including one with no captions; no YouTube controls appear in the crops; and capture works from both the hotkey and the side panel button (see the permissions note in section 3).

### Phase 2 — Identify (week 3)

1. Define `ProductCandidate` in Pydantic: `brand`, `model`, `category`, `color`, `confidence`, `evidence` (`visual` / `transcript` / `description`), `search_queries`, `visual_notes`.
2. Tier 1 node on `qwen/qwen3.8-27b` with JSON mode, validated against the Pydantic schema. Retry once on invalid JSON.
3. Tier 2 node on `openai/gpt-oss-120b`, called only when confidence < threshold or there are multiple candidates.
4. Rate limiter (per-model token bucket) and record/replay mode in `app/llm/`.
5. Identify cache in Postgres.
6. Optional: keep the identify and disambiguate prompts in **Langfuse prompt management**, and use the Langfuse prompt version as `prompt_version` in the eval cache key, so every eval result is tied to an exact prompt.
7. **Start the eval set now:** label 50 video moments (`video_id`, `timestamp`, correct brand + model, product URL). Store in `eval/labels.jsonl`.

**Done when:** you have Tier 1 and Tier 1+2 accuracy numbers on the 50-item set.

### Phase 3 — Retrieve (week 4)

1. `retailers/base.py`: `async def search(query: str) -> list[Listing]`, with a common `Listing` schema (title, price, shipping, currency, url, image_url, gtin/upc/mpn when present, seller, condition).
2. eBay Browse adapter (OAuth client-credentials token, cached until expiry).
3. Best Buy adapter.
4. LangGraph wiring: `identify → fan_out_to_retailers (Send) → retrieve → resolve`, with `listings: Annotated[list, operator.add]` in the state.
5. Cache retailer responses by query for 24h (protects free-tier API quotas too).

**Done when:** a trigger returns raw listings from both retailers in the side panel.

### Phase 4 — Resolve and verify (week 5–6)

1. Dedupe: group by GTIN/UPC/MPN; fall back to `rapidfuzz` title similarity + same brand.
2. SigLIP rerank: embed the video crop and each listing's image; store listing embeddings in pgvector so repeat products are free. Blend image score + text-match score.
3. Price breakdown: item + shipping + estimated sales tax by state (labeled as an estimate). Filter accessories ("case for", "compatible with").
4. `check_quality` node: rule-based first (top image score, brand present in title); call `gpt-oss-20b` only when rules are unsure.
5. `refine` node on `gpt-oss-20b`, capped by an `attempts` counter (max 2). Clear `listings` before re-retrieval.

**Done when:** top-1 and top-5 exact-match accuracy are measured end to end on the 50-item set.

### Phase 5 — UX and trust (week 7)

1. SSE streaming: `graph.astream(stream_mode="updates")` → event stream → side panel status line ("Found … · checking eBay…").
2. Product card with grouped listings, cheapest total price highlighted.
3. "Why this match": the transcript quote, description link, and image-similarity score that drove the result.
4. Sponsorship flag: paid-promo label, disclosure phrases in the transcript ("sponsored by", "use code", "link in description"), affiliate link patterns in the description. Use `gpt-oss-20b` only for ambiguous cases.
5. Error states: no captions, rate-limited ("try again in N seconds"), nothing found.

**Done when:** a non-technical friend can use it on a video without explanation.

### Phase 6 — Evaluate and ship (week 8–10)

1. Grow the eval set to 200 moments (mix of tech, fashion, home, beauty; regular videos and Shorts).
2. Eval runner: top-1 / top-5 accuracy, p50 / p95 latency, tokens per query, cache hit rate. Results cached per `(item, prompt_version, model)`.
   - Store the labeled set as a **Langfuse dataset** and run each config as a dataset run, so configs can be compared side by side in the Langfuse UI.
   - Attach scores to each run's trace (`top1_correct`, `top5_correct`, `latency_ms`). Scores count toward the 50k monthly units, so budget for full 200-item runs.
3. Ablations: frame only · transcript only · description only · all combined · Tier 1 only vs. Tier 1+2.
4. Tune the Tier 2 confidence threshold using the eval set (accuracy vs. calls-per-query curve).
5. Deploy the backend (Fly.io / Railway / Render) with managed Postgres + pgvector.
6. Publish Screen to Cart to the Chrome Web Store as unlisted ($5 one-time developer fee). Search the store for the name first; if it's taken, list it as "Screen to Cart for YouTube".
7. Write-up: architecture, eval table, ablation chart, cost and latency numbers.

Spread full 200-item runs across days because of the 200K tokens/day limit.

---

## 7. Moving to paid models later

Because every node gets its model from `get_llm(role)`, the switch is one install plus configuration. Run `uv add langchain-anthropic`, set `ANTHROPIC_API_KEY`, then change the model names:

```env
# free
IDENTIFY_VISION_MODEL=groq:qwen/qwen3.8-27b
DISAMBIGUATE_MODEL=groq:openai/gpt-oss-120b
REFINE_MODEL=groq:openai/gpt-oss-20b

# paid
IDENTIFY_VISION_MODEL=anthropic:claude-haiku-5-5
DISAMBIGUATE_MODEL=anthropic:claude-sonnet-5-5
REFINE_MODEL=anthropic:claude-haiku-5-5
```

When you switch:

1. Re-run the full eval set on the paid config and compare against the Groq baseline — this comparison is a strong result on its own.
2. Tier 2 can become a second **vision** call (Sonnet looks at the image directly), so re-tune the threshold.
3. Remove the aggressive input trimming if accuracy improves without it.
4. Keep record/replay mode; it's still useful for UI work.
5. Change the Langfuse tag from `groq-free` to `anthropic`, so you can filter and compare traces from before and after the switch.

Keep prompts provider-agnostic (plain JSON schema in the prompt + Pydantic validation) so they work on both.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Free-tier limits block development | Caching, record/replay, 50-item dev subset, per-model rate limiter |
| Groq changes or retires the vision model | Model names live in config; check the Groq vision docs at each phase |
| YouTube page changes break the content script | Isolate DOM selectors in one module; side panel UI is unaffected |
| No captions on a video | Fall back to frame + description; show lower confidence |
| Wrong exact model (lookalikes) | Transcript + description evidence, SigLIP rerank, "why this match" shown to user |
| Retailer API quota or downtime | 24h query cache; each adapter fails independently |
| Langfuse free-tier units run out | ~10–15 units per pipeline run fits well within 50k/month at Groq's free-tier volume; if you outgrow it, self-host Langfuse (free, MIT) or move to a paid plan |
| Privacy concerns | Send only the cropped video frame; don't store frames by default; say so in the listing |
