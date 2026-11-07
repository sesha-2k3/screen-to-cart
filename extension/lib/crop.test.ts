import { describe, expect, it } from 'vitest';
import { cropBox } from './crop';

const viewport = { viewportWidth: 1200, viewportHeight: 800 };

describe('cropBox', () => {
  it('scales the rect on a 2x display', () => {
    const rect = { left: 100, top: 50, width: 640, height: 360, ...viewport };

    expect(cropBox(rect, 2400, 1600)).toEqual({ x: 200, y: 100, width: 1280, height: 720 });
  });

  it('uses the screenshot size, so browser zoom is handled', () => {
    // 1x display at 150% zoom: CSS viewport is 1200 wide, screenshot is 1800.
    const rect = { left: 0, top: 0, width: 600, height: 400, ...viewport };

    expect(cropBox(rect, 1800, 1200)).toEqual({ x: 0, y: 0, width: 900, height: 600 });
  });

  it('clamps a video that is partly scrolled out of view', () => {
    const rect = { left: 0, top: -100, width: 1200, height: 675, ...viewport };

    expect(cropBox(rect, 1200, 800)).toEqual({ x: 0, y: 0, width: 1200, height: 575 });
  });
});
