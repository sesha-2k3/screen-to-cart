import { useEffect, useState } from 'react';
import type { CaptureState, FailureReason } from '@/lib/capture';

export default function CaptureButton({ state }: { state: CaptureState | undefined }) {
  const shortcut = useShortcut();
  const busy = state?.status === 'capturing';

  return (
    <section>
      <button disabled={busy} onClick={() => browser.runtime.sendMessage({ type: 'capture' })}>
        What’s this?
      </button>
      {busy && <p>Capturing…</p>}
      {state?.status === 'failed' && <p>{failureText(state.reason, state.message, shortcut)}</p>}
    </section>
  );
}

function failureText(reason: FailureReason, message: string, shortcut: string | undefined): string {
  if (reason === 'needs_shortcut') {
    return shortcut
      ? `Press ${shortcut} on the video to capture. The button works after that.`
      : 'Set a shortcut for Screen to Cart in chrome://extensions/shortcuts, then press it on the video.';
  }
  if (reason === 'reload_tab') return 'Reload the YouTube tab, then try again.';
  return message;
}

// Chrome formats the shortcut for the platform (⌥⇧S on macOS) and reflects user rebinds.
function useShortcut(): string | undefined {
  const [shortcut, setShortcut] = useState<string>();
  useEffect(() => {
    browser.commands.getAll().then((commands) => {
      setShortcut(commands.find((command) => command.name === 'capture')?.shortcut || undefined);
    });
  }, []);
  return shortcut;
}
