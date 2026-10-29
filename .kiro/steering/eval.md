---
inclusion: manual
---

# Evaluation guide (type #eval to include)

- Labeled set: `backend/eval/labels.jsonl`, one object per line: `video_id`, `timestamp`, `brand`, `model`, `product_url`, `category`, `is_short`.
- Dev subset: first 50 items (`--subset dev`). Full set: 200 items, run only at milestones and spread across days because of the 200K tokens/day limit.
- Metrics: top-1 and top-5 exact match, p50/p95 latency, tokens per query, cache hit rate.
- Ablations: frame only · transcript only · description only · all combined · Tier 1 only vs Tier 1+2.
- Store the set as a Langfuse dataset; each config is a dataset run. Attach scores `top1_correct`, `top5_correct`, `latency_ms`.
- Cache results per `(eval_item_id, prompt_version, model)` so unchanged configs cost nothing to rerun.
- Reports: write a markdown table and charts (pandas + matplotlib) to `backend/eval/reports/`.
