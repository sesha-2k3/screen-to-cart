// The isolated content script can't see the page's JS objects, so it asks the
// MAIN-world script through window events. Payloads are JSON strings because
// object details don't reliably cross the world boundary.
import type { PlayerData } from './playerData';
import type { TranscriptSegment } from './transcript';

interface PageRequests {
  playerData: { params: null; result: PlayerData | null };
  transcript: { params: { t: number }; result: TranscriptSegment[] };
}

type RequestType = keyof PageRequests;
type Handlers = { [K in RequestType]: (params: PageRequests[K]['params']) => Promise<PageRequests[K]['result']> };

const REQUEST_EVENT = 'screen-to-cart:request';
const RESPONSE_EVENT = 'screen-to-cart:response';

export function requestFromPage<K extends RequestType>(
  type: K,
  params: PageRequests[K]['params'],
  timeoutMs = 8000,
): Promise<PageRequests[K]['result']> {
  const id = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => finish(() => reject(new Error(`${type} timed out`))), timeoutMs);
    const onResponse = (event: Event) => {
      const reply = JSON.parse((event as CustomEvent<string>).detail);
      if (reply.id !== id) return;
      finish(() => (reply.error ? reject(new Error(reply.error)) : resolve(reply.result)));
    };
    const finish = (settle: () => void) => {
      clearTimeout(timer);
      window.removeEventListener(RESPONSE_EVENT, onResponse);
      settle();
    };
    window.addEventListener(RESPONSE_EVENT, onResponse);
    window.dispatchEvent(new CustomEvent(REQUEST_EVENT, { detail: JSON.stringify({ id, type, params }) }));
  });
}

export function servePageRequests(handlers: Handlers): void {
  window.addEventListener(REQUEST_EVENT, async (event) => {
    const { id, type, params } = JSON.parse((event as CustomEvent<string>).detail);
    const handler = handlers[type as RequestType] as (params: unknown) => Promise<unknown>;
    let reply: { id: string; result?: unknown; error?: string };
    try {
      reply = { id, result: await handler(params) };
    } catch (error) {
      reply = { id, error: String(error) };
    }
    window.dispatchEvent(new CustomEvent(RESPONSE_EVENT, { detail: JSON.stringify(reply) }));
  });
}
