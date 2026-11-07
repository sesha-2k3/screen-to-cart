import { useEffect, useState } from 'react';
import { CAPTURE_RESULT_KEY, type CaptureResult } from '@/lib/capture';

export default function CaptureButton() {
  const [result, setResult] = useState<CaptureResult>();
  const [shortcut, setShortcut] = useState<string>();

  useEffect(() => {
    browser.storage.session.get(CAPTURE_RESULT_KEY).then((items) => {
      setResult(items[CAPTURE_RESULT_KEY] as CaptureResult | undefined);
    });
    // Chrome returns the shortcut formatted for the platform (⌥⇧S on macOS), including user rebinds.
    browser.commands.getAll().then((commands) => {
      setShortcut(commands.find((c) => c.name === 'capture')?.shortcut || undefined);
    });
    const onChanged = (changes: Record<string, { newValue?: unknown }>) => {
      const change = changes[CAPTURE_RESULT_KEY];
      if (change) setResult(change.newValue as CaptureResult);
    };
    browser.storage.session.onChanged.addListener(onChanged);
    return () => browser.storage.session.onChanged.removeListener(onChanged);
  }, []);

  return (
    <section>
      <button onClick={() => browser.runtime.sendMessage({ type: 'capture' })}>
        What’s this?
      </button>
      {result?.ok && <p>{result.trigger}: captured ({result.bytes} bytes)</p>}
      {result && !result.ok && (
        <p>
          {shortcut
            ? `Press ${shortcut} on the video to capture. The button works after that.`
            : 'Set a shortcut for Screen to Cart in chrome://extensions/shortcuts, then press it on the video.'}
        </p>
      )}
    </section>
  );
}
