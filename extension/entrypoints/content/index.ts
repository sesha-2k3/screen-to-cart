import { serveContentRequests } from '@/lib/messages';
import { requestFromPage } from '@/lib/youtube/bridge';
import { drawFrame } from '@/lib/youtube/frame';
import { AD_SHOWING_SELECTOR, VIDEO_SELECTOR } from '@/lib/youtube/selectors';

const SEEK_TIMEOUT_MS = 2000;

export default defineContentScript({
  matches: ['https://www.youtube.com/*'],
  main() {
    serveContentRequests({
      pause: async () => {
        if (document.querySelector(AD_SHOWING_SELECTOR)) {
          throw new Error('An ad is playing. Wait for it to finish, then try again.');
        }
        const video = findVideo();
        video.pause();
        return { t: video.currentTime };
      },
      frameAt: async ({ time }) => {
        const video = findVideo();
        await seekTo(video, time);
        return drawFrame(video);
      },
      restore: async ({ time }) => {
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
