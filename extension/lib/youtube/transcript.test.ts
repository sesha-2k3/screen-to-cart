import { describe, expect, it } from 'vitest';
import { parseJson3, sliceAround } from './transcript';

describe('parseJson3', () => {
  it('joins segments into text and converts milliseconds to seconds', () => {
    const body = JSON.stringify({
      events: [
        { tStartMs: 0, dDurationMs: 5000 }, // window definition, no text
        { tStartMs: 12340, dDurationMs: 3200, segs: [{ utf8: 'this is' }, { utf8: ' the\nmouse' }] },
        { tStartMs: 15540, dDurationMs: 100, segs: [{ utf8: '\n' }] },
      ],
    });

    expect(parseJson3(body)).toEqual([{ start: 12.34, duration: 3.2, text: 'this is the mouse' }]);
  });

  it('returns null for the empty body YouTube sends without a token', () => {
    expect(parseJson3('')).toBeNull();
  });

  it('returns null for a body that is not json3', () => {
    expect(parseJson3('<transcript><text start="1">hi</text></transcript>')).toBeNull();
  });
});

describe('sliceAround', () => {
  const segments = [
    { start: 0, duration: 4, text: 'intro' },
    { start: 68, duration: 4, text: 'ends just inside' },
    { start: 100, duration: 4, text: 'at t' },
    { start: 130, duration: 4, text: 'starts at the edge' },
    { start: 140, duration: 4, text: 'too late' },
  ];

  it('keeps segments that overlap 30 seconds either side of t', () => {
    expect(sliceAround(segments, 100).map((s) => s.text)).toEqual([
      'ends just inside',
      'at t',
      'starts at the edge',
    ]);
  });
});
