import { servePageRequests } from '@/lib/youtube/bridge';
import { captureCaptionResponses } from '@/lib/youtube/captionCapture';
import { findPlayer, readPlayerData } from '@/lib/youtube/playerData';

export default defineContentScript({
  matches: ['https://www.youtube.com/*'],
  world: 'MAIN',
  // document_start so the fetch/XHR wrappers are in place before the player loads captions.
  runAt: 'document_start',
  main() {
    captureCaptionResponses();
    servePageRequests({
      playerData: async () => {
        const player = findPlayer();
        return player ? readPlayerData(player) : null;
      },
      transcript: async () => [],
    });
  },
});
