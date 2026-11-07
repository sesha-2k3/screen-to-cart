import { api, BACKEND_URL } from '@/lib/api';
import type { components } from '@/lib/api-types';
import { CAPTURE_STATE_KEY, type CaptureState, type Trigger } from '@/lib/capture';
import { sendToContent } from '@/lib/messages';
import { videoIdFromUrl } from '@/lib/youtube/videoId';

type Tab = Browser.tabs.Tab;
type LookupResult = components['schemas']['LookupResult'];

const FRAME_OFFSETS_SECONDS = [0, 0.5, 1.0];

let capturing = false;

export default defineBackground(() => {
  browser.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

  browser.commands.onCommand.addListener((command, tab) => {
    if (command !== 'capture' || tab?.id === undefined) return;
    // sidePanel.open only works inside the user gesture, so it must run before any await.
    browser.sidePanel.open({ tabId: tab.id });
    void runCapture(tab, 'hotkey');
  });

  browser.runtime.onMessage.addListener((message: unknown) => {
    if ((message as { type?: string })?.type !== 'capture') return;
    void browser.tabs
      .query({ active: true, lastFocusedWindow: true })
      .then(([tab]) => tab && runCapture(tab, 'button'));
  });
});

async function runCapture(tab: Tab, trigger: Trigger): Promise<void> {
  if (capturing) return;
  capturing = true;
  try {
    await setState({ status: 'capturing', trigger });
    await setState(await capture(tab));
  } catch (error) {
    await setState(failure(error));
  } finally {
    capturing = false;
  }
}

async function capture(tab: Tab): Promise<CaptureState> {
  const videoId = videoIdFromUrl(tab.url);
  if (!videoId || tab.id === undefined) {
    return { status: 'failed', reason: 'not_a_video', message: 'Open a YouTube video or Short first.' };
  }
  const { t } = await sendToContent(tab.id, 'pause', null);
  const cached = await lookup(videoId, t);
  if (cached) return { status: 'cached', result: cached };

  const frames = await captureFrames(tab.id, t);
  const { player, transcript } = await sendToContent(tab.id, 'context', { t });
  return {
    status: 'captured',
    capture: {
      id: crypto.randomUUID(),
      videoId,
      t,
      frames,
      title: player?.title ?? tab.title ?? '',
      description: player?.description ?? '',
      paidPromotion: player?.paidPromotion ?? false,
      transcript,
    },
  };
}

// Resolves to undefined on a miss (404).
async function lookup(videoId: string, t: number): Promise<LookupResult | undefined> {
  try {
    const { data } = await api.GET('/lookup', { params: { query: { video_id: videoId, t } } });
    return data;
  } catch {
    throw new Error(`Backend unreachable at ${BACKEND_URL}`);
  }
}

async function captureFrames(tabId: number, t: number): Promise<string[]> {
  const frames: string[] = [];
  try {
    for (const offset of FRAME_OFFSETS_SECONDS) {
      frames.push(await sendToContent(tabId, 'frameAt', { time: Math.max(0, t - offset) }));
    }
  } finally {
    await sendToContent(tabId, 'restore', { time: t });
  }
  return frames;
}

function failure(error: unknown): CaptureState {
  const message = error instanceof Error ? error.message : String(error);
  // The content script isn't in tabs that were open before the extension was installed or reloaded.
  if (message.includes('Receiving end does not exist')) return { status: 'failed', reason: 'reload_tab', message };
  return { status: 'failed', reason: 'other', message };
}

function setState(state: CaptureState): Promise<void> {
  return browser.storage.session.set({ [CAPTURE_STATE_KEY]: state });
}
