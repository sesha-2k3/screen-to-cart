// Every YouTube selector lives here, so a YouTube page change is a one-file fix.

export const PLAYER_ID = { watch: 'movie_player', shorts: 'shorts-player' } as const;

export const VIDEO_SELECTOR = { watch: '#movie_player video', shorts: '#shorts-player video' } as const;

// The player gets this class while an ad plays in place of the video.
export const AD_SHOWING_SELECTOR = '#movie_player.ad-showing';
