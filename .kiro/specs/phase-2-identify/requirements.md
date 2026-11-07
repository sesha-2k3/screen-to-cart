# Requirements Document

## Introduction

Phase 2 of the Screen to Cart build plan (`docs/screen-to-cart-build-plan.md`, section 6 Phase 2 steps 1–7, and the free-tier rules in section 2) identifies the product in the captured moment: a vision model proposes candidates, a text model disambiguates when needed, and results are cached and measured on a labeled set. Pipeline rules are in the `langgraph-pipeline` steering file, quota rules in `free-tier-budget`, eval conventions in `eval`. This document only adds what the plan leaves open.

Phase 2 is done when there are Tier 1 and Tier 1+2 accuracy numbers on the 50-item set.

Out of scope: retailer search (Phase 3), the sponsorship check (Phase 5), the full status-line UX (Phase 5), Langfuse datasets and scores, ablations and threshold tuning (Phase 6). Plan step 6 (Langfuse prompt management) is optional and skipped; `prompt_version` is a constant in code (design, Prompts).

## Glossary

- **Backend**: The FastAPI application in `backend/app/`.
- **Extension**, **Side_Panel**: As in Phase 1.
- **Candidate**: A `ProductCandidate`, one guess at the product (brand, model and supporting evidence).
- **Tier_1**: The identify node, which calls the `identify_vision` model with one image.
- **Tier_2**: The disambiguate node, which calls the `disambiguate` model with text only.
- **Tier_2_Rule**: Tier_1's top confidence is below `TIER2_CONFIDENCE_THRESHOLD`, or Tier_1 returned more than one Candidate.
- **Rate_Limiter**: The per-model token bucket in `backend/app/llm/`.
- **Fixture**: A stored LLM response in `fixtures/llm/`, used by `LLM_MODE=record` and `replay`.
- **Identify_Cache**: The Postgres table of final Candidates keyed by `video_id` and 5-second bucket (`floor(t / 5)`).
- **Eval_Capture**: A saved `/identify` request (sharpest frame and context) in `backend/eval/captures/`.
- **Eval_Runner**: `python -m eval.run` in `backend/eval/`.

## Requirements

### Requirement 1: Candidate schema

**User Story:** As the developer, I want one Pydantic model for a product guess, so that LLM output and the API payload can't drift apart.

#### Acceptance Criteria

1. THE Backend SHALL define `ProductCandidate` in `schemas.py` with `brand`, `model`, `category`, `color`, `confidence` (0–1), `evidence`, `search_queries` and `visual_notes`.
2. THE Backend SHALL give each evidence item a `source` of `visual`, `transcript` or `description`, and a short `detail`.
3. THE Backend SHALL use the same model to validate LLM output and to send Candidates to the Extension.

### Requirement 2: Tier 1 identify

**User Story:** As a viewer, I want the product in the frame named, so that I know exactly what I'm looking at.

#### Acceptance Criteria

1. WHEN `/identify` has picked the sharpest frame, THE Tier_1 node SHALL send exactly one image plus the title, trimmed description and transcript to the `identify_vision` model in JSON mode.
2. THE Tier_1 node SHALL validate the model's output against the Candidate schema.
3. IF the output is invalid JSON or fails validation, THEN THE Tier_1 node SHALL retry once.
4. IF the retry also fails, THEN THE Backend SHALL end the stream with an `upstream_error` event.

### Requirement 3: Tier 2 disambiguate

**User Story:** As a viewer, I want a second opinion when the first guess is unsure, so that I get the exact model and not a lookalike.

#### Acceptance Criteria

1. WHEN the Tier_2_Rule holds, THE Tier_2 node SHALL run on the `disambiguate` model.
2. WHEN the Tier_2_Rule doesn't hold, THE Backend SHALL skip the Tier_2 node.
3. THE Tier_2 node SHALL send no image, only Tier_1's Candidates and visual notes plus the same text context.
4. THE Tier_2 node SHALL validate and retry its output as in Requirement 2.

### Requirement 4: Input trimming

**User Story:** As the developer, I want model inputs kept small, so that each call fits the free-tier token budget.

#### Acceptance Criteria

1. THE Backend SHALL send at most 1,500 characters of the description to either model.
2. WHEN the description is trimmed, THE Backend SHALL keep lines with links or model-number-like words first.
3. THE Backend SHALL send the ±30 s transcript window the Extension already provides, unchanged.

### Requirement 5: Rate limiter

**User Story:** As the developer, I want each model's token budget respected, so that the free tier doesn't block requests with avoidable 429s.

#### Acceptance Criteria

1. THE Rate_Limiter SHALL keep one token bucket per model, sized from its tokens-per-minute limit.
2. WHEN a response arrives, THE Rate_Limiter SHALL set the bucket from the `x-ratelimit-remaining-tokens` header.
3. IF the bucket would wait more than 20 s, THEN THE Backend SHALL end the stream with a `rate_limited` event and the wait as `retry_after_seconds`.
4. IF the model returns HTTP 429, THEN THE Backend SHALL not retry, and SHALL end the stream with a `rate_limited` event carrying `retry_after_seconds` from the `retry-after` header.

### Requirement 6: Record and replay

**User Story:** As the developer, I want to reuse real model responses, so that UI work, tests and repeat evals use no quota.

#### Acceptance Criteria

1. WHILE `LLM_MODE=record`, WHEN a Fixture exists for the exact request, THE Backend SHALL return it without calling the model.
2. WHILE `LLM_MODE=record`, WHEN no Fixture exists, THE Backend SHALL call the model and store the response as a Fixture.
3. WHILE `LLM_MODE=replay`, THE Backend SHALL only read Fixtures, and IF none exists, THEN SHALL fail with an error naming the missing Fixture.
4. THE Backend SHALL NOT write image data into a Fixture.

### Requirement 7: Identify cache

**User Story:** As a viewer, I want a moment someone already asked about answered instantly, so that I don't wait and no quota is used.

#### Acceptance Criteria

1. WHEN a stream finishes without an error, THE Backend SHALL store the final Candidates in the Identify_Cache.
2. WHEN `GET /lookup` finds an entry for the `video_id` and bucket, THE Backend SHALL return it; otherwise it SHALL return 404.
3. IF the database is unreachable, THEN THE Backend SHALL treat lookups as misses, skip writes, and still complete the request.

### Requirement 8: Streaming and display

**User Story:** As a viewer, I want results to appear as soon as each step finishes, so that I see the product name without waiting for everything.

#### Acceptance Criteria

1. THE Backend SHALL stream `frame_selected`, then a `candidates` event after Tier_1, and another after Tier_2 when it runs.
2. IF a step fails, THEN THE Backend SHALL stream an `error` event with a `code` instead.
3. WHEN Candidates arrive from the stream or from a cache hit, THE Side_Panel SHALL show the top Candidate and the others as chips.
4. WHEN an `error` event arrives, THE Side_Panel SHALL show the message for its code (design, Error Handling).

### Requirement 9: Eval set

**User Story:** As the developer, I want labeled real captures, so that accuracy is measured on the inputs the extension actually sends.

#### Acceptance Criteria

1. WHILE `SAVE_EVAL_CAPTURES=true`, THE Backend SHALL save each `/identify` request, with only the sharpest frame, as an Eval_Capture.
2. THE repository SHALL gitignore `backend/eval/captures/`.
3. THE user SHALL label 50 captured moments in `backend/eval/labels.jsonl`, with the fields from the `eval` steering file.

### Requirement 10: Accuracy

**User Story:** As the developer, I want Tier 1 and Tier 1+2 accuracy numbers, so that I know what Tier 2 adds for its extra calls.

#### Acceptance Criteria

1. WHEN `uv run python -m eval.run --subset dev` runs, THE Eval_Runner SHALL run Tier_1 and the Tier_2_Rule on the first 50 labeled items.
2. THE Eval_Runner SHALL write a report to `backend/eval/reports/` with Tier 1 top-1 accuracy, Tier 1+2 top-1 accuracy and the share of items that called Tier_2.
