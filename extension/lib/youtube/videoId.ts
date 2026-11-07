/** YouTube video ID from a watch or Shorts URL, or null for any other page. */
export function videoIdFromUrl(url: string | undefined): string | null {
  if (!url) return null;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.hostname !== 'www.youtube.com') return null;
  if (parsed.pathname === '/watch') return parsed.searchParams.get('v') || null;
  const shorts = parsed.pathname.match(/^\/shorts\/([\w-]+)/);
  return shorts?.[1] ?? null;
}
