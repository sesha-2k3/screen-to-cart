# Design: Phase 1 Capture

Only the decisions the build plan doesn't already make.

## 1. Transcript: use the player's own caption request (deviation from the plan)

The plan says to fetch the caption track's `baseUrl` from the browser. Since mid-2025 YouTube requires a Proof-of-Origin token (`pot`) on `/api/timedtext`, and without it the request returns HTTP 200 with an empty body ([Stack Overflow](https://stackoverflow.com/questions/79668836/youtube-caption-extract-timedtext-api-pot-parameter), [yt-dlp #13075](https://github.com/yt-dlp/yt-dlp/issues/13075)). A September 2026 test from a residential IP got the same empty response ([dev.to](https://dev.to/xixisuperman/getting-youtube-transcripts-without-the-data-api-and-why-translate-to-100-languages-is-usually-43m8)). The token comes from YouTube's BotGuard script, so the extension can't generate it.

The approach: let the player make the request and read a copy of its response ([write-up of the technique](https://zenn.dev/naikaku01/articles/3605496d6d0ea6)).

- A MAIN-world content script (`entrypoints/player.content.ts`, `world: 'MAIN'`, `runAt: 'document_start'`) wraps `fetch` and `XMLHttpRequest`, and stores a copy (`response.clone()`) of every `/api/timedtext` response, keyed by video ID. It never changes or blocks the player's requests.
- When the transcript is needed, it tries these in order and stops at the first one that returns events:
  1. The stored response for this video.
  2. A direct fetch of the track's `baseUrl` with `fmt=json3`. This still works in some environments.
  3. If the player hasn't loaded captions (CC is off), turn subtitles on through the player API, wait for the stored response (timeout 3 s), then turn them off again. The captions overlay is hidden by the capture CSS, and this step runs after the frames are captured.
- If none of these return events, the transcript is empty and the panel shows "No captions".

Alternatives considered:
- Scraping the "Show transcript" panel: Shorts don't show it, and it means clicking through the page UI.
- Fetching on the backend with yt-dlp: breaks the "transcript is fetched in the browser" rule, and YouTube blocks datacenter IPs.

The same MAIN-world script reads the player response (`movie_player.getPlayerResponse()`, or `#shorts-player` on Shorts) for the title, `shortDescription`, caption tracks and the paid-content overlay. This works on Shorts, where the description isn't in the DOM, and stays current after YouTube's in-page navigation. The paid-promo flag is read from `paidContentOverlay` in the player response. This was confirmed on a video showing the "Includes paid promotion" banner, and on several videos without it.

If an ad is playing (the player has the `ad-showing` class), the capture stops and asks the user to wait, because the screenshot would show the ad instead of the video.

The isolated content script and the MAIN-world script talk through `window` `CustomEvent`s (request/response with a request ID).

## 2. Where each step runs

| Step | Runs in | Why |
|---|---|---|
| Video ID, rect, pause/seek, hide/restore controls | Isolated content script | DOM access; selectors live in `lib/youtube/selectors.ts`, shared by both content scripts |
| Player data, transcript | MAIN-world content script | Needs page JS objects and the player's network calls |
| `GET /lookup`, `captureVisibleTab`, crop | Background service worker | Only the background can capture; `OffscreenCanvas` works there |
| `POST /identify` (SSE) | Side panel | `@microsoft/fetch-event-source` calls `window.setTimeout` and `document`, which don't exist in a service worker |

The background writes the finished capture (3 crops + context) to `chrome.storage.session`. The side panel reads it on mount and watches `storage.onChanged`. When the hotkey opens a closed panel, the capture can finish before the panel has loaded, and this avoids that race. Three JPEG crops are well under the 10 MB `storage.session` quota.

## 3. Capture details

- Before each capture, the content script seeks, waits for `seeked`, then waits two animation frames so the hidden controls and the new frame are painted.
- Controls are hidden by toggling a class on `<html>` that enables an injected stylesheet. The hidden elements are the top and bottom chrome, the gradients, the caption window, the paid-promo overlay and the Shorts overlay. Restore always runs in a `finally` block.
- Crop scale is `bitmap.width / window.innerWidth`, not `devicePixelRatio` alone, so that browser zoom is handled too. The rect is clamped to the viewport.
- JPEG quality is 0.85.

## 4. Backend API for Phase 1

- `GET /lookup?video_id&t` returns 404 for now. Phase 2 adds the cache behind it.
- `POST /identify` accepts `IdentifyRequest` (`video_id`, `t`, `frames`: 1–3 base64 JPEGs, `title`, `description`, `transcript`: list of `{start, duration, text}`, `paid_promotion`). It returns an SSE stream with one `frame_selected` event (`FrameSelected { index, sharpness }`). Phase 2 adds more events to the same stream. `FrameSelected` is listed in the route's `responses` for `text/event-stream`, so `openapi-typescript` generates its type.
- A frame that won't decode returns 422.
- `vision/frame_select.py` decodes each frame with OpenCV, converts it to grayscale and scores it by the variance of the Laplacian. It is decorated with `@observe(capture_input=False)` so base64 images don't go to Langfuse. That keeps them private and doesn't use up units.

## 5. Permissions and the side panel button

Add `activeTab`, `storage` and host permission `https://www.youtube.com/*`. `storage` isn't in the plan's table but `chrome.storage.session` needs it. `scripting` isn't added: content scripts are declared in the manifest, and YouTube tabs that were open before install just need a reload.

Result of the task 1 test on macOS Chrome, regular videos and Shorts:
- The hotkey captured every time.
- The side panel button captured every time it was pressed, including after moving to another video or Short.
- The panel once showed "Either the '<all_urls>' or 'activeTab' permission is required." for the button path, but not from a button press during the test. The cause isn't known. Host permission for `youtube.com` alone isn't enough for `captureVisibleTab`, so this error is what any capture without an `activeTab` grant would show.

So the button stays as the normal trigger. If a capture fails, the panel tells the user to press the shortcut, reading its label from `commands.getAll()` (⌥⇧S on macOS, or whatever the user rebound it to). Task 10 checks the button again on 20 videos. `<all_urls>` is not added without asking (see the `extension` steering file).
