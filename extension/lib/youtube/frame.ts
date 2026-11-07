const JPEG_QUALITY = 0.85;
// Caps 4K frames so three of them stay well under chrome.storage.session's 10 MB quota.
// The vision model counts every image as the same number of tokens, so larger frames don't help.
const MAX_LONG_EDGE = 1280;

/** Scale a video size down so its long edge is at most MAX_LONG_EDGE. */
export function frameSize(videoWidth: number, videoHeight: number): { width: number; height: number } {
  const scale = Math.min(1, MAX_LONG_EDGE / Math.max(videoWidth, videoHeight));
  return { width: Math.round(videoWidth * scale), height: Math.round(videoHeight * scale) };
}

/**
 * The video's current frame as a JPEG data URL. Drawing the <video> element
 * itself, rather than taking a screenshot, means YouTube's overlays can't appear.
 */
export function drawFrame(video: HTMLVideoElement): string {
  if (!video.videoWidth || !video.videoHeight) throw new Error('The video hasn’t loaded yet. Try again.');
  const { width, height } = frameSize(video.videoWidth, video.videoHeight);
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  canvas.getContext('2d')!.drawImage(video, 0, 0, width, height);
  try {
    return canvas.toDataURL('image/jpeg', JPEG_QUALITY);
  } catch {
    // A SecurityError here means the browser won't expose the pixels, e.g. protected content.
    throw new Error('This video can’t be captured.');
  }
}
