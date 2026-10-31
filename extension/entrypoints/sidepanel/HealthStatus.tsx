import { useEffect, useState } from 'react';
import { api, BACKEND_URL } from '@/lib/api';
import { healthStatusFrom, type HealthStatus as Status } from './healthStatus';

export default function HealthStatus() {
  const [status, setStatus] = useState<Status>('checking');

  useEffect(() => {
    // StrictMode mounts effects twice in dev; drop results from the discarded mount.
    let mounted = true;

    async function check() {
      let next: Status;
      try {
        const { response } = await api.GET('/health');
        next = healthStatusFrom(response);
      } catch (error) {
        next = healthStatusFrom(error instanceof Error ? error : new Error(String(error)));
      }
      if (mounted) setStatus(next);
    }

    check();
    return () => {
      mounted = false;
    };
  }, []);

  if (status === 'checking') return <p>Checking backend…</p>;
  if (status === 'ok') return <p>backend OK</p>;
  return <p>Backend unreachable at {BACKEND_URL}</p>;
}
