# Requirements Document

## Introduction

Phase 1 of the Screen to Cart build plan (`docs/screen-to-cart-build-plan.md`, section 6 Phase 1 steps 1–5, and the request flow in section 3) captures the moment the user asks about: the video is paused, three frames and the page context are captured, and the backend picks the sharpest frame. Capture rules are in the `extension` steering file. This document only adds what the plan leaves open.

Phase 1 is done when it works on 10 regular videos and 10 Shorts, including one with no captions; no YouTube controls or overlays appear in the frames; and capture works from both the hotkey and the side panel button.

Out of scope: LLM calls, the identify cache, retailer search, description trimming (Phase 2), and the full SSE pipeline (Phase 5).

## Glossary

- **Extension**: The WXT + React + TypeScript Manifest V3 extension in `extension/`.
- **Side_Panel**: The Extension's React UI in `extension/entrypoints/sidepanel/`.
- **Backend**: The FastAPI application in `backend/app/`.
- **Trigger**: The `chrome.commands` hotkey or the Side_Panel's "What's this?" button.
- **t**: The video's current time, in seconds, when the Trigger fires.
- **Frame**: A JPEG image drawn from the page's `<video>` element onto a canvas.
- **Context**: Video ID, title, description, paid-promotion flag and the transcript segments within ±30 s of t.

## Requirements

### Requirement 1: Trigger

**User Story:** As a viewer, I want to start a capture from a hotkey or a button, so that I can ask about a product without leaving the video.

#### Acceptance Criteria

1. WHEN the hotkey is pressed or the "What's this?" button is clicked, THE Extension SHALL start the same capture flow.
2. WHEN the hotkey is pressed while the Side_Panel is closed, THE Extension SHALL open the Side_Panel.

### Requirement 2: Freeze the moment

**User Story:** As a viewer, I want the video to stop where I asked, so that the capture shows exactly the moment I meant.

#### Acceptance Criteria

1. WHEN the Trigger fires, THE Extension SHALL record t and pause the video.
2. WHEN a capture finishes or fails, THE Extension SHALL leave the video at t and paused.

### Requirement 3: Cache check

**User Story:** As a viewer, I want repeat questions answered from the cache, so that nothing is captured or uploaded when it isn't needed.

#### Acceptance Criteria

1. WHEN the Trigger fires, THE Extension SHALL call `GET /lookup?video_id&t` before capturing any Frame.
2. THE Backend SHALL return 404 from `GET /lookup` until the identify cache exists (Phase 2).
3. WHEN `GET /lookup` returns 404, THE Extension SHALL treat it as a miss and capture.

### Requirement 4: Frames

**User Story:** As a viewer, I want clean frames of the video itself, so that YouTube's overlays never confuse identification.

#### Acceptance Criteria

1. WHEN the lookup is a miss, THE Extension SHALL capture 3 Frames at t, t−0.5 s and t−1.0 s, clamped at 0, by seeking back.
2. THE Extension SHALL draw each Frame from the `<video>` element, so that no YouTube control or overlay appears in it (design, Frames).
3. THE Extension SHALL scale each Frame to a long edge of at most 1280 px and encode it as JPEG.
4. IF an ad is playing, THEN THE Extension SHALL capture no Frame and ask the user to wait for the ad to end.

### Requirement 5: Context

**User Story:** As a viewer, I want the video's text sent with the frames, so that the product can be identified from what was said and written.

#### Acceptance Criteria

1. THE Extension SHALL read the video ID from both `/watch?v=` and `/shorts/<id>` URLs.
2. THE Extension SHALL read the title, description, paid-promotion flag and the transcript segments within ±30 s of t.
3. IF the video has no captions, THEN THE Extension SHALL send an empty transcript and THE Side_Panel SHALL show "No captions", not an error.

### Requirement 6: Frame selection

**User Story:** As the developer, I want the backend to keep only the sharpest frame, so that one image per vision call is enough.

#### Acceptance Criteria

1. WHEN `POST /identify` receives Frames and Context, THE Backend SHALL pick the Frame with the highest Laplacian variance and return only its index.
2. IF a Frame can't be decoded, THEN THE Backend SHALL return HTTP 422.
3. THE Backend SHALL NOT store Frames or send them to Langfuse.

### Requirement 7: Display

**User Story:** As a viewer, I want to see what was captured, so that I can check the extension saw the right moment.

#### Acceptance Criteria

1. WHEN the Backend returns the chosen Frame's index, THE Side_Panel SHALL show that Frame, the transcript snippet, the title, the raw description and whether the video is marked as paid promotion.
