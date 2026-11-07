# Implementation Plan: Phase 1 Capture

## Overview

Build plan Phase 1 steps 1–5. See `requirements.md` for scope and `design.md` for the decisions. Each task stays under about 200 lines of new code.

## Tasks

- [x] 1. Spike: capture permission from the hotkey and the side panel button
  - Add `activeTab`, `storage` and host `https://www.youtube.com/*` to `wxt.config.ts`; add a `chrome.commands` entry `capture` (suggested key `Alt+Shift+S`)
  - Background: on the command, open the side panel and call `captureVisibleTab` once. Side panel: a "What's this?" button that sends a message to the background, which does the same
  - The user loads the extension and tries both triggers, including after moving to a new video. Record the result in `design.md` section 5; if the button can't capture, it shows the hotkey hint instead
  - _Requirements: 1_

- [x] 2. Backend frame selection
  - `IdentifyRequest`, `TranscriptSegment`, `FrameSelected` in `schemas.py`
  - `app/vision/frame_select.py`: `select_sharpest(frames: list[str]) -> FrameSelected` (Laplacian variance, `@observe(capture_input=False)`); raises on undecodable input
  - Test: a sharp and a blurred image, the sharp one wins; an undecodable frame raises
  - _Requirements: 6_

- [ ] 3. Backend endpoints
  - `GET /lookup` returns 404; `POST /identify` returns an `EventSourceResponse` with one `frame_selected` event, inside `trace_attributes("identify", session_id=video_id)`; 422 on a bad frame
  - List `FrameSelected` in the route's `responses` so it appears in OpenAPI; regenerate `extension/lib/api-types.ts`
  - Test: posting two frames streams `frame_selected` with the sharp frame's index
  - _Requirements: 3, 6_

- [ ] 4. MAIN-world player script
  - `entrypoints/player.content.ts` (`world: 'MAIN'`, `document_start`): read the player response (title, `shortDescription`, caption tracks, paid-promo flag) for watch and Shorts players
  - Wrap `fetch`/XHR to store copies of `/api/timedtext` responses by video ID
  - `CustomEvent` request/response bridge to the isolated script
  - Check the paid-promo field on one sponsored video and note it in `design.md`
  - _Requirements: 5_

- [ ] 5. Transcript
  - Fallback chain from `design.md` section 1: stored response → direct `fmt=json3` fetch → subtitles on/off through the player API with a 3 s timeout → empty
  - Parse json3 `events` into `{start, duration, text}` and keep segments within ±30 s of `t`
  - _Requirements: 5_

- [ ] 6. Isolated content script
  - `entrypoints/content/selectors.ts` with every YouTube selector; `entrypoints/content/index.ts`
  - Video ID from `/watch?v=` and `/shorts/<id>`; video element rect; message handlers for pause, seek-and-wait (`seeked` + 2 animation frames), hide/restore overlays, get context (via the bridge)
  - _Requirements: 2, 4, 5_

- [ ] 7. Background capture flow
  - On trigger: pause and read `t` → `GET /lookup` (404 = miss) → for offsets 0, 0.5, 1.0 (clamped at 0): seek, capture, keep ≥500 ms between captures → restore controls and `currentTime = t` in `finally` → gather context and transcript
  - Crop each capture with `OffscreenCanvas` (scale `bitmap.width / innerWidth`, rect clamped), encode JPEG 0.85
  - Write `{ crops, context }` to `chrome.storage.session`
  - _Requirements: 2, 3, 4_

- [ ] 8. Side panel
  - Read the capture from `chrome.storage.session` on mount and on change; `POST /identify` through `lib/api.ts` with `@microsoft/fetch-event-source`
  - Show the status line, the chosen crop, title, paid-promo flag, transcript snippet (or "No captions") and the raw description. One component per file; keep `HealthStatus`
  - _Requirements: 7_

- [ ] 9. Checkpoint: automated checks
  - `uv run pytest -q`, `uv run ruff check .`, `uv run mypy app` in `backend/`; `pnpm compile`, `pnpm test` and `pnpm build` in `extension/`

- [ ] 10. Final checkpoint: Phase 1 "Done when" (the user runs this)
  - Needs Chrome and real YouTube pages, so the agent gives the checklist and waits for results
  - 10 regular videos and 10 Shorts, at least one without captions and one with paid promotion. For each one, record: hotkey OK, button OK, no controls in the crop, transcript shown or "No captions", video paused at `t`

## Notes

- Tests never call live services; frames in tests are generated with NumPy/OpenCV, not stored fixtures.
- The extension uses Vitest (`pnpm test`, with WXT's `WxtVitest` plugin). Only pure functions get tests: video ID parsing (task 6), json3 parsing with the ±30 s slice (task 5) and crop math (task 7). Test files sit next to the code as `*.test.ts`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "2", "4"] },
    { "id": 1, "tasks": ["3", "5", "6"] },
    { "id": 2, "tasks": ["7"] },
    { "id": 3, "tasks": ["8"] }
  ]
}
```
