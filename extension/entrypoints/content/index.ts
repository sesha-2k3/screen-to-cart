import { serveContentRequests, type VideoRect } from '@/lib/messages';
import { requestFromPage } from '@/lib/youtube/bridge';
import { OVERLAY_SELECTORS, VIDEO_SELECTOR } from '@/lib/youtube/selectors';

const CAPTURING_CLASS = 'screen-to-cart-capturing';
const SEEK_TIMEOUT_MS = 2000;

export default defineContentScript({
  matches: ['https://www.youtube.com/*'],
  main() {
    injectCaptureStyle();
    serveContentRequests({
      pause: async () => {
        const video = findVideo();
        video.pause();
        return { t: video.currentTime };
      },
      seek: async ({ time }) => {
        const video = findVideo();
        await seekTo(video, time);
        await nextPaint();
        return rectOf(video);
      },
      hideOverlays: async () => {
        document.documentElement.classList.add(CAPTURING_CLASS);
        await nextPaint();
        return null;
      },
      restore: async ({ time }) => {
        document.documentElement.classList.remove(CAPTURING_CLASS);
        const video = findVideo();
        video.currentTime = time;
        video.pause();
        return null;
      },
      context: async ({ t }) => ({
        player: await requestFromPage('playerData', null),
        transcript: await requestFromPage('transcript', { t }),
      }),
    });
  },
});

function injectCaptureStyle(): void {
  const style = document.createElement('style');
  const hidden = OVERLAY_SELECTORS.map((selector) => `html.${CAPTURING_CLASS} ${selector}`).join(',\n');
  style.textContent = `${hidden} { visibility: hidden !important; transition: none !important; }`;
  document.head.append(style);
}

function findVideo(): HTMLVideoElement {
  const selector = location.pathname.startsWith('/shorts/') ? VIDEO_SELECTOR.shorts : VIDEO_SELECTOR.watch;
  const video = document.querySelector<HTMLVideoElement>(selector);
  if (!video) throw new Error('No video found on this page');
  return video;
}

// Resolves on `seeked`, or after a timeout in case the event never fires.
function seekTo(video: HTMLVideoElement, time: number): Promise<void> {
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      video.removeEventListener('seeked', done);
      resolve();
    };
    const timer = setTimeout(done, SEEK_TIMEOUT_MS);
    video.addEventListener('seeked', done);
    video.currentTime = time;
  });
}

// Two animation frames: one for the style or frame change, one for it to be painted.
function nextPaint(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
}

function rectOf(video: HTMLVideoElement): VideoRect {
  const { left, top, width, height } = video.getBoundingClientRect();
  return { left, top, width, height, viewportWidth: window.innerWidth, viewportHeight: window.innerHeight };
}
