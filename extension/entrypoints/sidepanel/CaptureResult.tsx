import { useEffect, useState } from 'react';
import { identify } from '@/lib/api';
import type { components } from '@/lib/api-types';
import type { Capture } from '@/lib/capture';
import CandidateList from './CandidateList';

type FrameSelected = components['schemas']['FrameSelected'];
type CandidatesEvent = components['schemas']['CandidatesEvent'];
type ErrorEvent = components['schemas']['ErrorEvent'];

export default function CaptureResult({ capture }: { capture: Capture }) {
  const [selected, setSelected] = useState<FrameSelected>();
  const [identified, setIdentified] = useState<CandidatesEvent>();
  const [streamError, setStreamError] = useState<ErrorEvent>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    setSelected(undefined);
    setIdentified(undefined);
    setStreamError(undefined);
    setError(undefined);
    identify(
      {
        video_id: capture.videoId,
        t: capture.t,
        frames: capture.frames.map(withoutDataUrlPrefix),
        title: capture.title,
        description: capture.description,
        transcript: capture.transcript,
        paid_promotion: capture.paidPromotion,
      },
      { onFrameSelected: setSelected, onCandidates: setIdentified, onError: setStreamError },
      controller.signal,
    ).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => controller.abort();
  }, [capture]);

  return (
    <section>
      <p>{statusLine(selected, identified, streamError, error)}</p>
      {identified && <CandidateList candidates={identified.candidates} />}
      {selected && (
        <img
          src={capture.frames[selected.index]}
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

function statusLine(
  selected: FrameSelected | undefined,
  identified: CandidatesEvent | undefined,
  streamError: ErrorEvent | undefined,
  error: string | undefined,
): string {
  if (error) return `Couldn’t identify: ${error}`;
  if (streamError?.code === 'rate_limited') {
    return `Rate limited. Try again in ${Math.ceil(streamError.retry_after_seconds ?? 60)} seconds.`;
  }
  if (streamError) return 'Couldn’t identify the product. Try again.';
  if (!selected) return 'Choosing the sharpest frame…';
  if (!identified) return 'Identifying the product…';
  return identified.tier === 2 ? 'Double-checked with a second model.' : '';
}

// The backend expects bare base64, without the "data:image/jpeg;base64," prefix.
function withoutDataUrlPrefix(dataUrl: string): string {
  return dataUrl.slice(dataUrl.indexOf(',') + 1);
}

function formatTime(seconds: number): string {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}
