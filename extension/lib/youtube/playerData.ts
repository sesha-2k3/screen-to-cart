import { PLAYER_ID } from './selectors';

export interface CaptionTrack {
  baseUrl: string;
  languageCode: string;
  kind?: string;
}

export interface PlayerData {
  videoId: string;
  title: string;
  description: string;
  paidPromotion: boolean;
  captionTracks: CaptionTrack[];
}

// Only the fields of YouTube's player response that we read.
interface PlayerResponse {
  videoDetails?: { videoId?: string; title?: string; shortDescription?: string };
  captions?: { playerCaptionsTracklistRenderer?: { captionTracks?: CaptionTrack[] } };
  paidContentOverlay?: unknown;
}

export interface YouTubePlayer extends HTMLElement {
  getPlayerResponse(): PlayerResponse | undefined;
  isSubtitlesOn?(): boolean;
  toggleSubtitles?(): void;
}

export function findPlayer(): YouTubePlayer | null {
  const id = location.pathname.startsWith('/shorts/') ? PLAYER_ID.shorts : PLAYER_ID.watch;
  const player = document.getElementById(id) as YouTubePlayer | null;
  return typeof player?.getPlayerResponse === 'function' ? player : null;
}

export function readPlayerData(player: YouTubePlayer): PlayerData | null {
  const response = player.getPlayerResponse();
  const details = response?.videoDetails;
  if (!details?.videoId) return null;
  return {
    videoId: details.videoId,
    title: details.title ?? '',
    description: details.shortDescription ?? '',
    paidPromotion: Boolean(response?.paidContentOverlay),
    captionTracks: response?.captions?.playerCaptionsTracklistRenderer?.captionTracks ?? [],
  };
}
