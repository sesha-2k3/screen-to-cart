# Screen to Cart

Find anything you see in a video, compared across stores.

The full build plan is in [`docs/screen-to-cart-build-plan.md`](docs/screen-to-cart-build-plan.md).

## Setup

Copy `.env.example` to `.env` and `extension/.env.example` to `extension/.env`, then fill in the values below by hand. Never commit either `.env` file.

| Variable | File | Where to get the value | Required in Phase 0 |
|---|---|---|---|
| `GROQ_API_KEY` | `.env` | console.groq.com | No (no LLM calls in Phase 0; needed from Phase 2) |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | `.env` | the "Screen to Cart" Langfuse project settings | Yes, for the Phase 0 trace check; `/health` works without them |
| `CORS_ALLOWED_ORIGINS` | `.env` | `chrome-extension://<id>` from `chrome://extensions` after loading the extension | Yes |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `BESTBUY_API_KEY` | `.env` | the eBay and Best Buy developer portals | No (used from Phase 3) |
| `DATABASE_URL`, `IDENTIFY_VISION_MODEL`, `DISAMBIGUATE_MODEL`, `REFINE_MODEL`, `SPONSORSHIP_MODEL`, `LLM_MODE`, `LANGFUSE_BASE_URL`, `SIGLIP_MODEL` | `.env` | copy the non-secret values from `.env.example` | `DATABASE_URL` yes (host runs of Alembic); the rest no |
| `WXT_BACKEND_URL` | `extension/.env` | the backend URL, only if it is not `http://localhost:8000` | No |

**Setting `CORS_ALLOWED_ORIGINS`:** load the unpacked extension in Chrome, open `chrome://extensions`, copy the extension's ID, and set `CORS_ALLOWED_ORIGINS=chrome-extension://<id>` in `.env`. Separate multiple origins with commas.
