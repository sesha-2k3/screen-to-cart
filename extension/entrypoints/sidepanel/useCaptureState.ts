import { useEffect, useState } from 'react';
import { CAPTURE_STATE_KEY, type CaptureState } from '@/lib/capture';

export function useCaptureState(): CaptureState | undefined {
  const [state, setState] = useState<CaptureState>();

  useEffect(() => {
    browser.storage.session.get(CAPTURE_STATE_KEY).then((items) => {
      setState(items[CAPTURE_STATE_KEY] as CaptureState | undefined);
    });
    const onChanged = (changes: Record<string, { newValue?: unknown }>) => {
      const change = changes[CAPTURE_STATE_KEY];
      if (change) setState(change.newValue as CaptureState);
    };
    browser.storage.session.onChanged.addListener(onChanged);
    return () => browser.storage.session.onChanged.removeListener(onChanged);
  }, []);

  return state;
}
