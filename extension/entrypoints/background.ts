import { CAPTURE_RESULT_KEY, type CaptureResult, type Trigger } from '@/lib/capture';

export default defineBackground(() => {
  browser.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

  browser.commands.onCommand.addListener((command, tab) => {
    if (command !== 'capture' || tab?.id === undefined) return;
    // sidePanel.open only works inside the user gesture, so it must run before any await.
    browser.sidePanel.open({ tabId: tab.id });
    void capture(tab.windowId, 'hotkey');
  });

  browser.runtime.onMessage.addListener((message: unknown) => {
    if ((message as { type?: string })?.type !== 'capture') return;
    void browser.tabs
      .query({ active: true, lastFocusedWindow: true })
      .then(([tab]) => capture(tab?.windowId, 'button'));
  });
});

async function capture(windowId: number | undefined, trigger: Trigger): Promise<void> {
  let result: CaptureResult;
  try {
    const dataUrl = await browser.tabs.captureVisibleTab(windowId, { format: 'jpeg' });
    result = { trigger, ok: true, bytes: dataUrl.length, at: Date.now() };
  } catch (error) {
    result = { trigger, ok: false, error: String(error), at: Date.now() };
  }
  await browser.storage.session.set({ [CAPTURE_RESULT_KEY]: result });
}
