# Requirements: Phase 2 Identify

Source: build plan section 6, Phase 2 steps 1–7, and the free-tier rules in section 2. Pipeline rules are in the `langgraph-pipeline` steering file, quota rules in `free-tier-budget`, eval conventions in `eval`. This document only adds what the plan leaves open.

## Done when (from the plan)

You have Tier 1 and Tier 1+2 accuracy numbers on the 50-item set.

## Requirements

1. **Candidate schema.** `ProductCandidate` in `schemas.py` has `brand`, `model`, `category`, `color`, `confidence` (0–1), `evidence` (each item has a `source` of `visual`, `transcript` or `description`, and a short `detail`), `search_queries` and `visual_notes`. The same model validates LLM output and is sent to the extension.
2. **Tier 1.** The identify node sends exactly one image (the sharpest frame) plus title, trimmed description and the transcript to the `identify_vision` model in JSON mode. Output is validated against the schema; one retry on invalid JSON, then the request fails with `upstream_error`.
3. **Tier 2.** The disambiguate node runs on the `disambiguate` model only when Tier 1's top confidence is below `TIER2_CONFIDENCE_THRESHOLD` or Tier 1 returns more than one candidate. It is text-only and works from Tier 1's candidates and visual notes plus the same text context.
4. **Trimming.** The description sent to either model is at most 1,500 characters, keeping lines with links or product-like words first. The transcript is the ±30 s window the extension already sends.
5. **Rate limiter.** Each model has its own token bucket sized from its tokens-per-minute limit. The bucket is corrected from `x-ratelimit-remaining-tokens` after each response. On a 429 the request is not retried silently: the stream sends `rate_limited` with `retry_after_seconds` from `retry-after`.
6. **Record/replay.** `LLM_MODE=record` returns a stored response when one exists for the exact request, otherwise calls the model and stores the response. `LLM_MODE=replay` only reads stored responses and fails clearly on a miss. Stored responses go in `fixtures/llm/` and never contain the image.
7. **Identify cache.** The final candidates are stored in Postgres under `video_id` + 5 s bucket. `GET /lookup` returns them on a hit and 404 on a miss. If the database is unreachable, lookups count as misses and writes are skipped; the request still succeeds.
8. **Streaming.** `/identify` streams `frame_selected`, then a `candidates` event after Tier 1 and again after Tier 2 if it runs, or an `error` event. The side panel shows the top candidate and the others as chips, for fresh and cached results.
9. **Eval set.** With `SAVE_EVAL_CAPTURES=true`, `/identify` saves the request (sharpest frame and context) to `backend/eval/captures/`, which is gitignored. The user labels 50 captured moments in `backend/eval/labels.jsonl` (fields from the `eval` steering file).
10. **Accuracy.** `uv run python -m eval.run --subset dev` runs Tier 1 and the Tier 2 rule on each labeled item and writes a report to `backend/eval/reports/` with Tier 1 top-1 accuracy, Tier 1+2 top-1 accuracy and the share of items that called Tier 2.

## Out of scope

Retailer search (Phase 3), sponsorship check (Phase 5), the full status-line UX (Phase 5), Langfuse datasets and scores, ablations and threshold tuning (Phase 6). Plan step 6 (Langfuse prompt management) is optional and skipped; `prompt_version` is a constant in code (design, Prompts).
