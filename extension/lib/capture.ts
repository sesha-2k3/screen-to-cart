export type Trigger = 'hotkey' | 'button';

export type CaptureResult =
  | { trigger: Trigger; ok: true; bytes: number; at: number }
  | { trigger: Trigger; ok: false; error: string; at: number };

export const CAPTURE_RESULT_KEY = 'captureResult';
