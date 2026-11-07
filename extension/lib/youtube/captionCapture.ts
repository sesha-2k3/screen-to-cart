// YouTube's timedtext endpoint returns an empty body without a Proof-of-Origin
// token, which only the player can produce. So we keep a copy of the caption
// responses the player itself fetches (see design.md section 1). The player's
// requests are never changed or blocked.

const captionsByVideo = new Map<string, string>();

export function storedCaptions(videoId: string): string | undefined {
  return captionsByVideo.get(videoId);
}

export function captureCaptionResponses(): void {
  const originalFetch = window.fetch;
  window.fetch = async function (input, init) {
    const response = await originalFetch.call(this, input, init);
    const url = input instanceof Request ? input.url : String(input);
    if (isTimedtext(url)) {
      response.clone().text().then((body) => remember(url, body), () => {});
    }
    return response;
  };

  const originalOpen = XMLHttpRequest.prototype.open as (this: XMLHttpRequest, ...args: unknown[]) => void;
  XMLHttpRequest.prototype.open = function (this: XMLHttpRequest, ...args: unknown[]) {
    const url = String(args[1]);
    if (isTimedtext(url)) {
      this.addEventListener('load', () => {
        if (this.responseType === '' || this.responseType === 'text') remember(url, this.responseText);
      });
    }
    originalOpen.apply(this, args);
  } as typeof XMLHttpRequest.prototype.open;
}

function isTimedtext(url: string): boolean {
  return url.includes('/api/timedtext');
}

function remember(url: string, body: string): void {
  const videoId = new URL(url, location.href).searchParams.get('v');
  if (videoId && body) captionsByVideo.set(videoId, body);
}
