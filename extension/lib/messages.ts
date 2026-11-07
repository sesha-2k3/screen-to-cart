// Background ↔ isolated content script messages. Replies use sendResponse
// (wrapped as { ok, value | error }) because returning a Promise from an
// onMessage listener isn't supported in every Chrome version.
import type { PlayerData } from './youtube/playerData';
import type { TranscriptSegment } from './youtube/transcript';

export interface VideoRect {
  left: number;
  top: number;
  width: number;
  height: number;
  viewportWidth: number;
  viewportHeight: number;
}

interface ContentRequests {
  pause: { params: null; result: { t: number } };
  seek: { params: { time: number }; result: VideoRect };
  hideOverlays: { params: null; result: null };
  restore: { params: { time: number }; result: null };
  context: { params: { t: number }; result: { player: PlayerData | null; transcript: TranscriptSegment[] } };
}

type RequestType = keyof ContentRequests;
type Reply = { ok: true; value: unknown } | { ok: false; error: string };

export async function sendToContent<K extends RequestType>(
  tabId: number,
  type: K,
  params: ContentRequests[K]['params'],
): Promise<ContentRequests[K]['result']> {
  const reply = (await browser.tabs.sendMessage(tabId, { type, params })) as Reply | undefined;
  if (!reply) throw new Error(`No reply to ${type} from the page`);
  if (!reply.ok) throw new Error(reply.error);
  return reply.value as ContentRequests[K]['result'];
}

export function serveContentRequests(handlers: {
  [K in RequestType]: (params: ContentRequests[K]['params']) => Promise<ContentRequests[K]['result']>;
}): void {
  browser.runtime.onMessage.addListener((message: unknown, _sender, sendResponse) => {
    const { type, params } = message as { type: RequestType; params: unknown };
    const handler = handlers[type] as ((params: unknown) => Promise<unknown>) | undefined;
    if (!handler) return;
    handler(params).then(
      (value) => sendResponse({ ok: true, value } satisfies Reply),
      (error) => sendResponse({ ok: false, error: String(error) } satisfies Reply),
    );
    return true;
  });
}
