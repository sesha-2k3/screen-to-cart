---
inclusion: fileMatch
fileMatchPattern: ["backend/app/graph/**/*", "backend/app/llm/**/*"]
---

# LangGraph pipeline rules

## Graph shape
```
START → sponsorship_check (parallel branch, needs only promo label/transcript/description)
START → identify (Tier 1, vision) → [low confidence or several items] → disambiguate (Tier 2, text)
      → fan_out_to_retailers (Send, top candidate only) → retrieve (one per retailer)
      → resolve (dedupe, SigLIP rerank, price breakdown, attach sponsorship)
      → check_quality → "refine" → refine_query → fan_out_to_retailers   (max 2 refinements)
                      → "done"   → END
```

## State
- `PipelineState` is a `TypedDict` in `graph/state.py`.
- `listings: Annotated[list[Listing], operator.add]` so parallel retrieve results merge. Clear it when a refine starts.
- `attempts: int` caps the refine loop at 2.

## Nodes
- One node per file in `graph/nodes/`. A node takes state and returns only the fields it changes.
- LLM nodes get their model from `get_llm(role)` with roles `identify_vision`, `disambiguate`, `refine`, `sponsorship`.
- LLM output is validated against Pydantic models from `schemas.py`; retry once on invalid JSON, then fail the node with a clear error.
- `check_quality` is rule-based first (top image similarity, brand present in title); call the LLM only when the rules are unsure.
- Tier 2 runs only when Tier 1 confidence < `TIER2_CONFIDENCE_THRESHOLD` (from config) or Tier 1 returns several candidates.

## Streaming and tracing
- The endpoint runs `graph.astream(state, config={"callbacks": [handler]}, stream_mode="updates")` and forwards each update as an SSE event.
- Create a new Langfuse `CallbackHandler` per request; wrap the run in `propagate_attributes(trace_name="identify", session_id=video_id, tags=[provider])`.
