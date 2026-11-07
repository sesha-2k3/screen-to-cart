import type { VideoRect } from './messages';

const JPEG_QUALITY = 0.85;

export interface CropBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * The video's rect in screenshot pixels. Scales by screenshot width / viewport
 * width rather than devicePixelRatio alone, so browser zoom is handled too.
 */
export function cropBox(rect: VideoRect, imageWidth: number, imageHeight: number): CropBox {
  const scale = imageWidth / rect.viewportWidth;
  const left = clamp(Math.round(rect.left * scale), imageWidth);
  const top = clamp(Math.round(rect.top * scale), imageHeight);
  const right = clamp(Math.round((rect.left + rect.width) * scale), imageWidth);
  const bottom = clamp(Math.round((rect.top + rect.height) * scale), imageHeight);
  return { x: left, y: top, width: right - left, height: bottom - top };
}

/** Crop a captureVisibleTab screenshot to the video and return a JPEG data URL. */
export async function cropScreenshot(screenshot: string, rect: VideoRect): Promise<string> {
  const bitmap = await createImageBitmap(await (await fetch(screenshot)).blob());
  const box = cropBox(rect, bitmap.width, bitmap.height);
  if (box.width < 1 || box.height < 1) {
    bitmap.close();
    throw new Error('The video isn’t visible. Scroll it into view and try again.');
  }
  const canvas = new OffscreenCanvas(box.width, box.height);
  canvas.getContext('2d')!.drawImage(bitmap, box.x, box.y, box.width, box.height, 0, 0, box.width, box.height);
  bitmap.close();
  return blobToDataUrl(await canvas.convertToBlob({ type: 'image/jpeg', quality: JPEG_QUALITY }));
}

function clamp(value: number, max: number): number {
  return Math.min(Math.max(value, 0), max);
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}
