import { api, BACKEND_URL } from '@/lib/api';
import { CAPTURE_STATE_KEY, type CaptureState, type Trigger } from '@/lib/capture';
import { cropScreenshot } from '@/lib/crop';
import { sendToContent } from '@/lib/messages';
import { videoIdFromUrl } from '@/lib/youtube/videoId';

type Tab = Browser.tabs.Tab;

const FRAME_OFFSETS_SECONDS = [0, 0.5, 1.0];
// Chrome allows about 2 captureVisibleTab calls per second.
const MIN_CAPTURE_GAP_MS = 500;
const SCREENSHOT_JPEG_QUALITY = 95;

let capturing = false;
let lastCaptureAt = 0;

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
  if (await isCached(videoId, t)) return { status: 'cached', videoId, t };

  const crops = await captureFrames(tab.id, tab.windowId, t);
  const { player, transcript } = await sendToContent(tab.id, 'context', { t });
  return {
    status: 'captured',
    capture: {
      id: crypto.randomUUID(),
      videoId,
      t,
      crops,
      title: player?.title ?? tab.title ?? '',
      description: player?.description ?? '',
      paidPromotion: player?.paidPromotion ?? false,
      transcript,
    },
  };
}

async function isCached(videoId: string, t: number): Promise<boolean> {
  try {
    const { response } = await api.GET('/lookup', { params: { query: { video_id: videoId, t } } });
    return response.ok;
  } catch {
    throw new Error(`Backend unreachable at ${BACKEND_URL}`);
  }
}

// captureVisibleTab only sees what's on screen now, so earlier frames come from seeking back.
async function captureFrames(tabId: number, windowId: number, t: number): Promise<string[]> {
  const crops: string[] = [];
  await sendToContent(tabId, 'hideOverlays', null);
  try {
    for (const offset of FRAME_OFFSETS_SECONDS) {
      const rect = await sendToContent(tabId, 'seek', { time: Math.max(0, t - offset) });
      await sleep(lastCaptureAt + MIN_CAPTURE_GAP_MS - Date.now());
      lastCaptureAt = Date.now();
      const screenshot = await browser.tabs.captureVisibleTab(windowId, {
        format: 'jpeg',
        quality: SCREENSHOT_JPEG_QUALITY,
      });
      crops.push(await cropScreenshot(screenshot, rect));
    }
  } finally {
    await sendToContent(tabId, 'restore', { time: t });
  }
  return crops;
}

function failure(error: unknown): CaptureState {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes('activeTab')) return { status: 'failed', reason: 'needs_shortcut', message };
  // The content script isn't in tabs that were open before the extension was installed or reloaded.
  if (message.includes('Receiving end does not exist')) return { status: 'failed', reason: 'reload_tab', message };
  return { status: 'failed', reason: 'other', message };
}

function setState(state: CaptureState): Promise<void> {
  return browser.storage.session.set({ [CAPTURE_STATE_KEY]: state });
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)));
}
