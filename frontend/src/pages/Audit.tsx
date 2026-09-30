import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import { auditApi } from '../api/endpoints';
import type { AuditRow } from '../api/endpoints';
import { useAuth } from '../auth';

export function Audit() {
  const { me } = useAuth();
  const isAdmin = me?.role === 'admin';

  const [rows, setRows] = useState<AuditRow[]>([]);
  const [count, setCount] = useState(0);
  const [action, setAction] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string> = {};
      if (action) params.action = action;
      const page = await auditApi.list(params);
      setRows(page.results);
      setCount(page.count);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load audit log');
    } finally {
      setLoading(false);
    }
  }, [isAdmin, action]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isAdmin) {
    return (
      <div className="max-w-md rounded-lg border border-edge bg-panel px-4 py-3 text-xs text-muted">
        The audit log is admin-only.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <select
          value={action}
          onChange={(e) => setAction(e.target.value)}
          className="rounded-md border border-edge bg-panel2 px-2 py-1.5 text-xs text-ink"
        >
          <option value="">All actions</option>
          {['login', 'logout', 'create', 'update', 'delete', 'ingest'].map((a) => (
            <option key={a}>{a}</option>
          ))}
        </select>
        <span className="ml-auto text-xs text-faint">{count} event(s)</span>
      </div>

      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>
      )}

      <div className="overflow-hidden rounded-lg border border-edge bg-panel">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-edge text-[11px] uppercase tracking-wide text-faint">
            <tr>
              <th className="px-4 py-2.5 font-medium">Time</th>
              <th className="px-4 py-2.5 font-medium">Action</th>
              <th className="px-4 py-2.5 font-medium">Actor</th>
              <th className="px-4 py-2.5 font-medium">Object</th>
              <th className="px-4 py-2.5 font-medium">Details</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-muted">Loading…</td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-muted">No audit events yet.</td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-edge/60 last:border-0 hover:bg-panel2/60">
                <td className="whitespace-nowrap px-4 py-2.5 text-faint">
                  {new Date(r.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2.5 font-medium text-ink">{r.action}</td>
                <td className="px-4 py-2.5 text-muted">{r.actor ?? '—'}</td>
                <td className="px-4 py-2.5 font-mono text-muted">{r.object ?? '—'}</td>
                <td className="max-w-md truncate px-4 py-2.5 font-mono text-faint">
                  {[r.changes, r.metadata].filter((x) => Object.keys(x ?? {}).length).map((x) => JSON.stringify(x)).join(' ') || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
