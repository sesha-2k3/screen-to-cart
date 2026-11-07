import { describe, expect, it } from 'vitest';
import { videoIdFromUrl } from './videoId';

describe('videoIdFromUrl', () => {
  it('reads the v parameter on a watch page', () => {
    expect(videoIdFromUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s')).toBe('dQw4w9WgXcQ');
  });

  it('reads the path segment on a Shorts page', () => {
    expect(videoIdFromUrl('https://www.youtube.com/shorts/aB3_x-9Yz01?feature=share')).toBe('aB3_x-9Yz01');
  });

  it('returns null for pages that are not a video', () => {
    expect(videoIdFromUrl('https://www.youtube.com/')).toBeNull();
    expect(videoIdFromUrl('https://www.youtube.com/@somechannel')).toBeNull();
    expect(videoIdFromUrl('chrome://extensions')).toBeNull();
  });
});
