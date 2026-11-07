import { describe, expect, it } from 'vitest';
import { frameSize } from './frame';

describe('frameSize', () => {
  it('keeps a 720p frame as it is', () => {
    expect(frameSize(1280, 720)).toEqual({ width: 1280, height: 720 });
  });

  it('scales a 4K frame down to a 1280 long edge', () => {
    expect(frameSize(3840, 2160)).toEqual({ width: 1280, height: 720 });
  });

  it('uses the height as the long edge for a vertical Short', () => {
    expect(frameSize(1080, 1920)).toEqual({ width: 720, height: 1280 });
  });
});
