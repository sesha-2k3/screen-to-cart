import { useEffect, useState } from 'react';
import { identify } from '@/lib/api';
import type { components } from '@/lib/api-types';
import type { Capture } from '@/lib/capture';

type FrameSelected = components['schemas']['FrameSelected'];

export default function CaptureResult({ capture }: { capture: Capture }) {
  const [selected, setSelected] = useState<FrameSelected>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    setSelected(undefined);
    setError(undefined);
    identify(
      {
        video_id: capture.videoId,
        t: capture.t,
        frames: capture.crops.map(withoutDataUrlPrefix),
        title: capture.title,
        description: capture.description,
        transcript: capture.transcript,
        paid_promotion: capture.paidPromotion,
      },
      { onFrameSelected: setSelected },
      controller.signal,
    ).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => controller.abort();
  }, [capture]);

  return (
    <section>
      <p>{statusLine(selected, error, capture.crops.length)}</p>
      {selected && (
        <img
          src={capture.crops[selected.index]}
          alt="Chosen frame"
          style={{ width: '100%', borderRadius: 4 }}
        />
      )}
      <h2 style={{ fontSize: '1.1rem' }}>{capture.title}</h2>
      <p>{capture.paidPromotion ? 'Includes paid promotion' : 'No paid-promotion label'}</p>
      <h3>Transcript around {formatTime(capture.t)}</h3>
      {capture.transcript.length === 0 ? (
        <p>No captions</p>
      ) : (
        <blockquote style={{ margin: 0 }}>{capture.transcript.map((segment) => segment.text).join(' ')}</blockquote>
      )}
      <h3>Description</h3>
      <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{capture.description}</pre>
    </section>
  );
}

function statusLine(selected: FrameSelected | undefined, error: string | undefined, frameCount: number): string {
  if (error) return `Couldn’t pick a frame: ${error}`;
  if (!selected) return 'Choosing the sharpest frame…';
  return `Sharpest of ${frameCount} frames: frame ${selected.index + 1}`;
}

// The backend expects bare base64, without the "data:image/jpeg;base64," prefix.
function withoutDataUrlPrefix(dataUrl: string): string {
  return dataUrl.slice(dataUrl.indexOf(',') + 1);
}

function formatTime(seconds: number): string {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}
