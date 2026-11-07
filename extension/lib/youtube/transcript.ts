import type { components } from '@/lib/api-types';

export type TranscriptSegment = components['schemas']['TranscriptSegment'];

export const TRANSCRIPT_WINDOW_SECONDS = 30;

interface Json3 {
  events?: { tStartMs?: number; dDurationMs?: number; segs?: { utf8?: string }[] }[];
}

/** Parse a timedtext `fmt=json3` body. Returns null when the body isn't usable json3. */
export function parseJson3(body: string | undefined): TranscriptSegment[] | null {
  if (!body) return null;
  let data: Json3;
  try {
    data = JSON.parse(body);
  } catch {
    return null;
  }
  if (!Array.isArray(data.events)) return null;
  return data.events.flatMap((event) => {
    const text = (event.segs ?? []).map((seg) => seg.utf8 ?? '').join('').replace(/\s+/g, ' ').trim();
    if (!text || event.tStartMs === undefined) return [];
    return [{ start: event.tStartMs / 1000, duration: (event.dDurationMs ?? 0) / 1000, text }];
  });
}

export function sliceAround(
  segments: TranscriptSegment[],
  t: number,
  windowSeconds = TRANSCRIPT_WINDOW_SECONDS,
): TranscriptSegment[] {
  return segments.filter(
    (segment) => segment.start + segment.duration >= t - windowSeconds && segment.start <= t + windowSeconds,
  );
}
