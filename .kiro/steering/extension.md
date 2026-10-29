---
inclusion: fileMatch
fileMatchPattern: "extension/**/*"
---

# Extension conventions (WXT + React + TS, Manifest V3)

## Capture rules (these come from real browser constraints)
- Capture only on an explicit user action (hotkey via `chrome.commands`, or the side panel's "What's this?" button).
- On trigger: record `t`, pause the video, call `GET /lookup` first; capture only on a cache miss.
- `chrome.tabs.captureVisibleTab` only captures what is on screen *now*, and Chrome allows about **2 calls per second**. Capture `t`, then seek back to `t−0.5s` and `t−1.0s` (wait for the `seeked` event), keeping captures ≥ 0.5s apart.
- Hide YouTube's overlay controls during capture and restore them after. Restore `currentTime = t` and leave the video paused.
- Crop to the video element's rect scaled by `devicePixelRatio`, using `OffscreenCanvas` in the service worker. Encode JPEG. Only crops leave the browser.
- Fetch the transcript in the browser from the page's caption track; never from the backend.

## Permissions
`activeTab`, `sidePanel`, `scripting`, and host permission for `https://www.youtube.com/*`. Do not add `<all_urls>` without asking; it triggers a bigger install warning.

## Code conventions
- YouTube DOM selectors live in one module (`entrypoints/content/selectors.ts` or similar) so page changes are a one-file fix.
- API calls go through `lib/api.ts`. Streaming `/identify` uses `@microsoft/fetch-event-source` (POST + SSE); the built-in `EventSource` only supports GET.
- Never edit `lib/api-types.ts`; regenerate it with `pnpm openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts`.
- Side panel state updates incrementally per SSE event (status line, candidate chips, product card, price breakdown, sponsored flag, "why this match").
- Typographic quotes and apostrophes in user-facing text.
