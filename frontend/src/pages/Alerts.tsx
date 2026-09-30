import { useCallback, useEffect, useState } from 'react';

import { alertsApi } from '../api/endpoints';
import type { Alert } from '../api/endpoints';
import { ApiError } from '../api/client';
import { useAuth } from '../auth';
import { SeverityBadge, StatusPill } from '../components/badges';

const ALERT_STATUSES = ['New', 'In Progress', 'Suppressed', 'Resolved'];

export function Alerts() {
  const { me } = useAuth();
  const canEdit = me?.role !== 'viewer';

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [count, setCount] = useState(0);
  const [status, setStatus] = useState('');
  const [severity, setSeverity] = useState('');
  const [q, setQ] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string> = {};
      if (status) params.status = status;
      if (severity) params.severity = severity;
      if (q) params.q = q;
      const page = await alertsApi.list(params);
      setAlerts(page.results);
      setCount(page.count);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }, [status, severity, q]);

  useEffect(() => {
    void load();
  }, [load]);

  const changeStatus = async (alert: Alert, next: string) => {
    setAlerts((rows) => rows.map((r) => (r.id === alert.id ? { ...r, status: next } : r)));
    try {
      await alertsApi.patch(alert.id, { status: next });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Update failed');
      void load();
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search title / id…"
          className="w-56 rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink placeholder:text-faint focus:border-accent"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-md border border-edge bg-panel2 px-2 py-1.5 text-xs text-ink"
        >
          <option value="">All statuses</option>
          {ALERT_STATUSES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="rounded-md border border-edge bg-panel2 px-2 py-1.5 text-xs text-ink"
        >
          <option value="">All severities</option>
          {['Critical', 'High', 'Medium', 'Low', 'Informational'].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <span className="ml-auto text-xs text-faint">{count} alert(s)</span>
      </div>

      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>
      )}

      <div className="overflow-hidden rounded-lg border border-edge bg-panel">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-edge text-[11px] uppercase tracking-wide text-faint">
            <tr>
              <th className="px-4 py-2.5 font-medium">ID</th>
              <th className="px-4 py-2.5 font-medium">Severity</th>
              <th className="px-4 py-2.5 font-medium">Title</th>
              <th className="px-4 py-2.5 font-medium">Correlation</th>
              <th className="px-4 py-2.5 font-medium">Case</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted">Loading…</td>
              </tr>
            )}
            {!loading && alerts.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted">
                  No alerts yet. Ingest via POST /api/alerts/ or wait for your SIEM webhook.
                </td>
              </tr>
            )}
            {alerts.map((a) => (
              <tr key={a.id} className="border-b border-edge/60 last:border-0 hover:bg-panel2/60">
                <td className="px-4 py-2.5 font-mono text-faint">{a.alert_id}</td>
                <td className="px-4 py-2.5"><SeverityBadge value={a.severity} /></td>
                <td className="max-w-xs truncate px-4 py-2.5 text-ink" title={a.desc || a.title}>
                  {a.title}
                </td>
                <td className="px-4 py-2.5 font-mono text-muted">{a.correlation_uid || '—'}</td>
                <td className="px-4 py-2.5 font-mono text-muted">
                  {a.case_id_ref?.case_id ?? '—'}
                </td>
                <td className="px-4 py-2.5">
                  {canEdit ? (
                    <select
                      value={a.status}
                      onChange={(e) => void changeStatus(a, e.target.value)}
                      className="rounded border border-edge bg-panel2 px-1.5 py-1 text-xs text-ink"
                    >
                      {ALERT_STATUSES.map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  ) : (
                    <StatusPill value={a.status} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
