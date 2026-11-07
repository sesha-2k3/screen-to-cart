# Requirements: Phase 1 Capture

Source: build plan section 6, Phase 1 steps 1–5, and the request flow in section 3 (steps 1–8). Capture rules are in the `extension` steering file. This document only adds what the plan leaves open.

## Done when (from the plan)

It works on 10 regular videos and 10 Shorts, including one with no captions; no YouTube controls appear in the crops; and capture works from both the hotkey and the side panel button.

## Requirements

1. **Trigger.** The hotkey (`chrome.commands`) and the side panel's "What's this?" button both start the same capture flow. The hotkey also opens the side panel.
2. **Freeze.** On trigger the extension records `t` and pauses the video. After capture the video is at `t` and still paused.
3. **Cache check.** The extension calls `GET /lookup?video_id&t` before capturing. In Phase 1 the backend has no cache yet, so `/lookup` always returns 404 and the extension treats 404 as a miss. The identify cache arrives in Phase 2 step 5.
4. **Frames.** On a miss the extension takes 3 frames at `t`, `t−0.5s`, `t−1.0s` (clamped at 0), drawn from the video element so no YouTube overlay appears (design section 3), encoded as JPEG. No frames are taken while an ad is playing.
5. **Context.** The extension reads video ID (watch and Shorts URLs), title, description, paid-promotion flag, and the transcript segments within ±30 s of `t`. A video without captions yields an empty transcript and a "No captions" note, not an error.
6. **Frame selection.** `POST /identify` receives the frames and context and picks the sharpest frame by Laplacian variance. Only the index of the chosen frame is returned. Frames are not stored, and are not sent to Langfuse.
7. **Display.** The side panel shows the chosen frame, the transcript snippet, the title, the raw description and whether the video is marked as paid promotion.

## Out of scope

LLM calls, the identify cache, retailer search, description trimming (Phase 2), and the full SSE pipeline (Phase 5).
