# Design: Phase 1 Capture

## Overview

Phase 1 implements build plan section 6, Phase 1 steps 1–5, and the request flow in section 3. This document records only the decisions the plan doesn't already make. Two of them depart from the plan:

- **Transcript:** a direct fetch of the caption track returns an empty body, so the extension reads the player's own caption responses (see Transcript below).
- **Frames:** frames are drawn from the `<video>` element instead of `captureVisibleTab` screenshots, so YouTube's overlays can't appear (see Frames below).

## Architecture

| Step | Runs in | Why |
|---|---|---|
| Video ID, pause/seek, draw frames, ad check | Isolated content script (`entrypoints/content/index.ts`) | DOM access; selectors live in `lib/youtube/selectors.ts`, shared by both content scripts |
| Player data, transcript | MAIN-world content script (`entrypoints/player.content.ts`) | Needs page JS objects and the player's network calls |
| Trigger, `GET /lookup`, orchestration | Background service worker (`entrypoints/background.ts`) | Receives the hotkey and opens the side panel |
| `POST /identify` (SSE) | Side panel | `@microsoft/fetch-event-source` calls `window.setTimeout` and `document`, which don't exist in a service worker |

The background writes the finished capture (3 frames + context) to `chrome.storage.session`. The side panel reads it on mount and watches `storage.onChanged`. When the hotkey opens a closed panel, the capture can finish before the panel has loaded, and this avoids that race.

The isolated content script and the MAIN-world script talk through `window` `CustomEvent`s (`lib/youtube/bridge.ts`, request/response with a request ID). The background and the isolated script use `runtime` messages (`lib/messages.ts`).

## Components and Interfaces

### Transcript: the player's own caption requests (deviation from the plan)

The plan says to fetch the caption track's `baseUrl` from the browser. Since mid-2025 YouTube requires a Proof-of-Origin token (`pot`) on `/api/timedtext`, and without it the request returns HTTP 200 with an empty body ([Stack Overflow](https://stackoverflow.com/questions/79668836/youtube-caption-extract-timedtext-api-pot-parameter), [yt-dlp #13075](https://github.com/yt-dlp/yt-dlp/issues/13075)). A September 2026 test from a residential IP got the same empty response ([dev.to](https://dev.to/xixisuperman/getting-youtube-transcripts-without-the-data-api-and-why-translate-to-100-languages-is-usually-43m8)). The token comes from YouTube's BotGuard script, so the extension can't generate it.

The approach: let the player make the request and read a copy of its response ([write-up of the technique](https://zenn.dev/naikaku01/articles/3605496d6d0ea6)).

- The MAIN-world script (`world: 'MAIN'`, `runAt: 'document_start'`) wraps `fetch` and `XMLHttpRequest`, and stores a copy (`response.clone()`) of every `/api/timedtext` response, keyed by video ID. It never changes or blocks the player's requests.
- When the transcript is needed, it tries these in order and stops at the first one that returns events:
  1. The stored response for this video.
  2. A direct fetch of the track's `baseUrl` with `fmt=json3`. This still works in some environments.
  3. If the player hasn't loaded captions (CC is off), turn subtitles on through the player API, wait for the stored response (timeout 3 s), then turn them off again. This runs after the frames are taken, and captions on the page can't appear in frames drawn from the video element anyway.
- Human-written tracks are preferred over auto-generated (`kind: 'asr'`) ones. Segments within ±30 s of `t` are kept.

Alternatives considered:
- Scraping the "Show transcript" panel: Shorts don't show it, and it means clicking through the page UI.
- Fetching on the backend with yt-dlp: breaks the "transcript is fetched in the browser" rule, and YouTube blocks datacenter IPs.

### Player data

The MAIN-world script reads the player response (`movie_player.getPlayerResponse()`, or `#shorts-player` on Shorts) for the title, `shortDescription`, caption tracks and the paid-promotion flag. This works on Shorts, where the description isn't in the DOM, and stays current after YouTube's in-page navigation.

The paid-promotion flag is `paidContentOverlay` in the player response. It was confirmed on two videos showing the "Includes paid promotion" banner, and on several without it.

### Frames: draw the video element (deviation from the plan)

The plan captures frames with `chrome.tabs.captureVisibleTab` and crops them to the video in the service worker. That was built first, and in the first Chrome check YouTube's overlays still showed up in the crops: the Shorts channel name, Subscribe button, title and progress bar, the info-card icon and channel watermarks. Hiding them by CSS selector meant chasing YouTube's markup.

Instead, the content script draws the `<video>` element onto a canvas (`lib/youtube/frame.ts`). Overlays are separate elements, so they can't appear. YouTube plays through Media Source Extensions, so the canvas isn't tainted; a console test on a real video confirmed `toDataURL` works. This also removed the overlay CSS, the crop math, Chrome's 2-captures-per-second limit and the `activeTab` permission.

- Seek to the target time, wait for `seeked` (2 s timeout), then draw. Restore `currentTime = t` and pause in a `finally` block.
- Long edge capped at 1280 px, so three 4K frames stay well under the 10 MB `storage.session` quota. The vision model counts every image as the same number of tokens, so a larger frame doesn't help.
- JPEG quality 0.85.

### Backend API

- `GET /lookup?video_id&t` returns 404 for now. Phase 2 adds the cache behind it.
- `POST /identify` accepts an `IdentifyRequest` and returns an SSE stream with one `frame_selected` event. Phase 2 adds more events to the same stream. `FrameSelected` is listed in the route's `responses` for `text/event-stream`, so `openapi-typescript` generates its type.
- `vision/frame_select.py` decodes each frame with OpenCV, converts it to grayscale and scores it by the variance of the Laplacian. It is decorated with `@observe(capture_input=False)` so base64 images don't go to Langfuse. That keeps them private and doesn't use up units.

### Permissions

`sidePanel`, `storage` and host permission `https://www.youtube.com/*`. `storage` isn't in the plan's table but `chrome.storage.session` needs it. `scripting` isn't added: content scripts are declared in the manifest, and YouTube tabs that were open before install just need a reload. `activeTab` was needed only for `captureVisibleTab` and was removed with it.

Task 1 tested `captureVisibleTab` from the hotkey and the button; both worked. The panel once showed an `activeTab` permission error from the button path that couldn't be reproduced. Drawing the video element doesn't need that permission, so the error can no longer happen.

## Data Models

API payloads are Pydantic models in `backend/app/schemas.py`; the extension uses the types generated from them in `lib/api-types.ts`.

| Model | Fields |
|---|---|
| `IdentifyRequest` | `video_id`, `t`, `frames` (1–3 base64 JPEGs without a `data:` prefix), `title`, `description`, `transcript`, `paid_promotion` |
| `TranscriptSegment` | `start`, `duration` (seconds), `text` |
| `FrameSelected` | `index` of the sharpest frame, `sharpness` |

Extension-only state (`lib/capture.ts`), stored in `chrome.storage.session` under `captureState`:

| State | Contents |
|---|---|
| `capturing` | which trigger started it |
| `cached` | `videoId`, `t` (can't happen until Phase 2) |
| `captured` | a `Capture`: `id`, `videoId`, `t`, `frames` (data URLs in order `t`, `t−0.5s`, `t−1.0s`), `title`, `description`, `paidPromotion`, `transcript` |
| `failed` | a reason (`not_a_video`, `reload_tab`, `other`) and a message |

## Correctness Properties

- The frame with the highest Laplacian variance is the one returned.
- After a capture, success or failure, the video is at `t` and paused.
- Only frames drawn from the video element leave the browser; no page screenshot is taken.
- Nothing is captured while an ad is playing.

These are checked by the tests below and the manual Chrome check. No property-based tests (see `engineering.md`).

## Error Handling

| Situation | What the user sees |
|---|---|
| Not on a watch or Shorts page | "Open a YouTube video or Short first." |
| Content script missing (tab open before install or reload) | "Reload the YouTube tab, then try again." |
| An ad is playing | "An ad is playing. Wait for it to finish, then try again." |
| Video not loaded yet | "The video hasn’t loaded yet. Try again." |
| Pixels not readable (protected content) | "This video can’t be captured." No screenshot fallback until a real video needs it |
| Backend down | "Backend unreachable at …" |
| A frame won't decode | `/identify` returns 422; the panel shows "Couldn’t pick a frame: …" |
| No captions | Not an error: empty transcript, panel shows "No captions" |

## Testing Strategy

- Backend (`pytest`): the sharp frame beats blurred ones; undecodable frames are rejected; `/identify` streams the sharp frame's index and returns 422 on a bad frame. Frames are generated with NumPy/OpenCV.
- Extension (Vitest): video ID parsing, json3 parsing with the ±30 s slice, and the frame size cap.
- Manual (task 11): regular videos and Shorts in Chrome, checking both triggers, clean frames, transcript, paid-promotion flag and that the video stays paused at `t`.
