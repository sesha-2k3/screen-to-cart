import type { TranscriptSegment } from './youtube/transcript';

export type Trigger = 'hotkey' | 'button';

// Why a capture failed, so the side panel can show the right message.
export type FailureReason = 'not_a_video' | 'reload_tab' | 'other';

export interface Capture {
  id: string;
  videoId: string;
  t: number;
  frames: string[]; // JPEG data URLs, in order t, t−0.5s, t−1.0s
  title: string;
  description: string;
  paidPromotion: boolean;
  transcript: TranscriptSegment[];
}

export type CaptureState =
  | { status: 'capturing'; trigger: Trigger }
  | { status: 'cached'; videoId: string; t: number }
  | { status: 'captured'; capture: Capture }
  | { status: 'failed'; reason: FailureReason; message: string };

// Stored in chrome.storage.session so a side panel opened by the hotkey still
// gets a capture that finished before it loaded (design.md section 2).
export const CAPTURE_STATE_KEY = 'captureState';
