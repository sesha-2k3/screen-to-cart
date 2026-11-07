---
inclusion: fileMatch
fileMatchPattern: "extension/**/*"
---

# Extension conventions (WXT + React + TS, Manifest V3)

## Capture rules (these come from real browser constraints)
- Capture only on an explicit user action (hotkey via `chrome.commands`, or the side panel's "What's this?" button).
- On trigger: record `t`, pause the video, call `GET /lookup` first; capture only on a cache miss.
- Frames are drawn from the `<video>` element onto a canvas in the content script, not taken with `captureVisibleTab`, so YouTube's overlays can't appear (Phase 1 design, section 3). Take `t`, then seek back to `t−0.5s` and `t−1.0s`, waiting for the `seeked` event before each draw.
- Restore `currentTime = t` and leave the video paused.
- Don't capture while an ad is playing (`ad-showing` on the player).
- Long edge ≤ 1280 px, JPEG. Only these frames leave the browser.
- Fetch the transcript in the browser from the page's caption track; never from the backend.

## Permissions
`sidePanel`, `storage`, and host permission for `https://www.youtube.com/*`. Add others only when code needs them (`activeTab` was removed with `captureVisibleTab`). Do not add `<all_urls>` without asking; it triggers a bigger install warning.

## Code conventions
- YouTube DOM selectors live in one module (`entrypoints/content/selectors.ts` or similar) so page changes are a one-file fix.
- API calls go through `lib/api.ts`. Streaming `/identify` uses `@microsoft/fetch-event-source` (POST + SSE); the built-in `EventSource` only supports GET.
- Never edit `lib/api-types.ts`; regenerate it with `pnpm openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts`.
- Side panel state updates incrementally per SSE event (status line, candidate chips, product card, price breakdown, sponsored flag, "why this match").
- Typographic quotes and apostrophes in user-facing text.
