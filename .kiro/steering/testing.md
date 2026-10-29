---
inclusion: fileMatch
fileMatchPattern: ["backend/tests/**/*", "extension/**/*.test.*"]
---

# Testing rules

- Backend: `pytest` + `pytest-asyncio`. Run with `uv run pytest -q`.
- No live network in tests. LLMs: `LLM_MODE=replay` with fixtures. HTTP: `respx`. Live tests get `@pytest.mark.live` and are skipped by default.
- Every retailer adapter has tests for: normal results, empty results, HTTP error, and malformed payload.
- Every graph node has a unit test calling the node function directly with a hand-built state.
- `check_quality` and the refine loop have a test proving the loop stops after 2 attempts.
- Frame selection has a test with a sharp and a blurred image proving the sharp one wins.
- Name tests `test_<unit>_<behavior>`.
