export type HealthStatus = 'checking' | 'ok' | 'unreachable';

export function healthStatusFrom(result: { ok: boolean; status?: number } | Error): HealthStatus {
  if (result instanceof Error) return 'unreachable';
  return result.ok && result.status === 200 ? 'ok' : 'unreachable';
}
