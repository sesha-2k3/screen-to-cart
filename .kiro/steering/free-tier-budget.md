---
inclusion: auto
name: free-tier-budget
description: Groq free-tier rate limits and the rules for not wasting quota. Use when writing or running anything that calls an LLM, writing tests, running evals, or adding caching and rate limiting.
---

# Free-tier budget rules

Groq free-plan limits per model (check the console, they vary by account): about 30 requests/min, 1K requests/day, 8K tokens/min, 200K tokens/day. One identify call is about 4K tokens (each image counts as 2,048), so the real budget is roughly **2 identify calls per minute and ~50 per day**.

## Rules
- Tests never call live LLMs or retailer APIs. Use `LLM_MODE=replay` with fixtures in `fixtures/`, and `respx` for HTTP. Mark any test that needs live calls with `@pytest.mark.live`; it's skipped by default.
- Send exactly **one** image per vision call (the sharpest frame), never three.
- Cache identify results by `video_id + 5s bucket`, retailer results by query for 24h, and eval results by `(eval_item_id, prompt_version, model)`.
- Trim inputs: description ≤ ~1,500 characters (keep lines with links and product names first), transcript window ±30s.
- The per-model token bucket in `app/llm/` must read `x-ratelimit-remaining-tokens` and honor `retry-after` on 429.
- Use the 50-item dev subset for evals (`--subset dev`). Never start a full 200-item eval run yourself; ask the user.
- Search only the top candidate automatically; other candidates are searched only when the user clicks them.
