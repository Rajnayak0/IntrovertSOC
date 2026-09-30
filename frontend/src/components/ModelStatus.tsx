import { useCallback, useEffect, useState } from 'react';

import { modelApi } from '../api/endpoints';
import type { ModelStatus } from '../api/endpoints';

const POLL_MS = 20_000;

export function useModelStatus(pollMs: number = POLL_MS) {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async (force = false) => {
    try {
      setStatus(await modelApi.status(force));
    } catch {
      setStatus({
        connected: false,
        base_url: '',
        model: '',
        detail: 'Backend unreachable',
        checked_at: Date.now() / 1000,
        banner: 'Backend unreachable — is the IntrovertSOC server running?',
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh(false);
    const id = setInterval(() => void refresh(false), pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  return { status, loading, refresh };
}

export function StatusDot({ status }: { status: ModelStatus | null }) {
  const cls = !status ? 'bg-faint' : status.connected ? 'bg-ok' : 'bg-danger';
  const label = !status
    ? 'Checking model server…'
    : status.connected
      ? `Model connected: ${status.server_model ?? status.model} (${status.base_url})`
      : status.banner ?? 'Local model server not detected';
  return (
    <span
      className={`inline-flex h-2.5 w-2.5 rounded-full ${cls}`}
      title={label}
      aria-label={label}
    />
  );
}
