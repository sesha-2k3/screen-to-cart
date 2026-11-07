import type { CaptureState, FailureReason } from '@/lib/capture';

export default function CaptureButton({ state }: { state: CaptureState | undefined }) {
  const busy = state?.status === 'capturing';

  return (
    <section>
      <button disabled={busy} onClick={() => browser.runtime.sendMessage({ type: 'capture' })}>
        What’s this?
      </button>
      {busy && <p>Capturing…</p>}
      {state?.status === 'failed' && <p>{failureText(state.reason, state.message)}</p>}
    </section>
  );
}

function failureText(reason: FailureReason, message: string): string {
  if (reason === 'reload_tab') return 'Reload the YouTube tab, then try again.';
  return message;
}
