---
inclusion: always
---

# Product: Screen to Cart

Screen to Cart is a Chrome extension (Manifest V3) that identifies products in a YouTube video or Short at the moment the user asks, then finds them across retailers with a price comparison, a sponsorship flag, and the evidence behind each match.

Tagline: "Find anything you see in a video, compared across stores."

## Who it's for
People watching product-heavy videos (reviews, hauls, tech, home, beauty) who want the exact item, not lookalikes, and want to know if the creator was paid to promote it.

## What makes it different
- Retailer-neutral: compares across stores, never favors one.
- Honest: flags sponsorship (YouTube's paid-promo label, disclosure phrases, affiliate links).
- Explainable: every match shows "why this match" evidence (transcript quote, description link, image similarity).

## How it works
1. User presses the hotkey or clicks "What's this?" in the side panel.
2. The video pauses; the extension checks the cache, and on a miss captures 3 frames (t, t−0.5s, t−1.0s by seeking back) plus transcript, title, description and the paid-promo label.
3. The FastAPI backend runs a LangGraph pipeline: identify → (disambiguate) → retrieve from retailers → resolve and rerank → verify/refine.
4. Results stream to the side panel over SSE as each step finishes.

## Non-goals
- No continuous screen monitoring. Capture only on an explicit user action.
- No checkout or buying on the user's behalf.
- No mobile app for now.
- No storing video frames by default.

## Source of truth
The full build plan is `docs/screen-to-cart-build-plan.md` (see the `build-plan` steering file). If a request conflicts with the plan, point out the conflict and ask before deviating.
