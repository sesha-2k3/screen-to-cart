// Every YouTube selector lives here, so a YouTube page change is a one-file fix.

export const PLAYER_ID = { watch: 'movie_player', shorts: 'shorts-player' } as const;

export const VIDEO_SELECTOR = { watch: '#movie_player video', shorts: '#shorts-player video' } as const;

// Hidden during capture so they don't end up in the crops.
export const OVERLAY_SELECTORS = [
  '.ytp-chrome-top',
  '.ytp-chrome-bottom',
  '.ytp-gradient-top',
  '.ytp-gradient-bottom',
  '.ytp-caption-window-container',
  '.ytp-paid-content-overlay',
  '.ytp-ce-element',
  '.ytp-cards-teaser',
  '.ytp-pause-overlay',
  '.ytp-bezel',
  '.ytp-spinner',
  '.ytp-tooltip',
  'ytd-reel-player-overlay-renderer',
];
