// Runs in the MAIN world. The fallback order is in design.md section 1.
import { storedCaptions } from './captionCapture';
import { findPlayer, readPlayerData, type CaptionTrack, type YouTubePlayer } from './playerData';
import { parseJson3, sliceAround, type TranscriptSegment } from './transcript';

const PLAYER_LOAD_TIMEOUT_MS = 3000;

export async function loadTranscript(t: number): Promise<TranscriptSegment[]> {
  const player = findPlayer();
  const data = player && readPlayerData(player);
  if (!player || !data) return [];
  const track = pickTrack(data.captionTracks);
  if (!track) return [];

  const segments =
    parseJson3(storedCaptions(data.videoId)) ??
    parseJson3(await fetchDirect(track)) ??
    parseJson3(await loadThroughPlayer(player, data.videoId));
  return segments ? sliceAround(segments, t) : [];
}

// Prefer captions written by a person over auto-generated (kind 'asr') ones.
function pickTrack(tracks: CaptionTrack[]): CaptionTrack | undefined {
  return tracks.find((track) => track.kind !== 'asr') ?? tracks[0];
}

async function fetchDirect(track: CaptionTrack): Promise<string | undefined> {
  const url = new URL(track.baseUrl, location.href);
  url.searchParams.set('fmt', 'json3');
  try {
    return await (await fetch(url)).text();
  } catch {
    return undefined;
  }
}

// When CC is off the player hasn't fetched captions, so turn them on briefly to
// make it fetch (with its token), and keep the copy captionCapture stores.
async function loadThroughPlayer(player: YouTubePlayer, videoId: string): Promise<string | undefined> {
  if (!player.toggleSubtitles || !player.isSubtitlesOn || player.isSubtitlesOn()) return undefined;
  player.toggleSubtitles();
  try {
    return await waitFor(() => storedCaptions(videoId), PLAYER_LOAD_TIMEOUT_MS);
  } finally {
    player.toggleSubtitles();
  }
}

async function waitFor<T>(read: () => T | undefined, timeoutMs: number): Promise<T | undefined> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = read();
    if (value !== undefined) return value;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return undefined;
}
