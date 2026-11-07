import { fetchEventSource } from '@microsoft/fetch-event-source';
import createClient from 'openapi-fetch';
import type { components, paths } from './api-types';

export const BACKEND_URL: string =
  import.meta.env.WXT_BACKEND_URL || 'http://localhost:8000';

export const api = createClient<paths>({ baseUrl: BACKEND_URL });

type IdentifyRequest = components['schemas']['IdentifyRequest'];
type FrameSelected = components['schemas']['FrameSelected'];

export interface IdentifyHandlers {
  onFrameSelected(frame: FrameSelected): void;
}

/** POST /identify and dispatch its SSE events. Resolves when the stream ends. */
export async function identify(
  body: IdentifyRequest,
  handlers: IdentifyHandlers,
  signal: AbortSignal,
): Promise<void> {
  await fetchEventSource(`${BACKEND_URL}/identify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
    // The side panel can be hidden while the stream is open; keep it open.
    openWhenHidden: true,
    async onopen(response) {
      if (!response.ok) throw new Error(`identify failed with HTTP ${response.status}`);
    },
    onmessage(message) {
      if (message.event === 'frame_selected') handlers.onFrameSelected(JSON.parse(message.data));
    },
    onerror(error) {
      // Rethrowing stops fetch-event-source from retrying the POST.
      throw error;
    },
  });
}
