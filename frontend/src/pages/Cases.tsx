import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { casesApi } from '../api/endpoints';
import type { CaseRow } from '../api/endpoints';
import { useAuth } from '../auth';
import { SeverityBadge, StatusPill } from '../components/badges';

export function Cases() {
  const { me } = useAuth();
  const navigate = useNavigate();
  const canEdit = me?.role !== 'viewer';

  const [rows, setRows] = useState<CaseRow[]>([]);
  const [count, setCount] = useState(0);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [title, setTitle] = useState('');
  const [severity, setSeverity] = useState('Medium');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string> = {};
      if (q) params.q = q;
      if (status) params.status = status;
      const page = await casesApi.list(params);
      setRows(page.results);
      setCount(page.count);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load cases');
    } finally {
      setLoading(false);
    }
  }, [q, status]);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async () => {
    if (!title.trim()) return;
    setCreating(true);
    setError('');
    try {
      const created = await casesApi.create({ title: title.trim(), severity });
      setTitle('');
      navigate(`/cases/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Create failed');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search cases…"
          className="w-56 rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink placeholder:text-faint focus:border-accent"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-md border border-edge bg-panel2 px-2 py-1.5 text-xs text-ink"
        >
          <option value="">All statuses</option>
          {['New', 'In Progress', 'On Hold', 'Resolved', 'Closed'].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <span className="ml-auto text-xs text-faint">{count} case(s)</span>
      </div>

      {canEdit && (
        <div className="flex items-center gap-2 rounded-lg border border-edge bg-panel px-3 py-2.5">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void create()}
            placeholder="New case title…"
            className="flex-1 rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink placeholder:text-faint focus:border-accent"
          />
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="rounded-md border border-edge bg-panel2 px-2 py-1.5 text-xs text-ink"
          >
            {['Critical', 'High', 'Medium', 'Low', 'Informational'].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void create()}
            disabled={creating || !title.trim()}
            className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
          >
            {creating ? 'Creating…' : 'Create'}
          </button>
        </div>
      )}

      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>
      )}

      <div className="overflow-hidden rounded-lg border border-edge bg-panel">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-edge text-[11px] uppercase tracking-wide text-faint">
            <tr>
              <th className="px-4 py-2.5 font-medium">ID</th>
              <th className="px-4 py-2.5 font-medium">Title</th>
              <th className="px-4 py-2.5 font-medium">Severity</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Alerts</th>
              <th className="px-4 py-2.5 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted">Loading…</td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted">No cases yet.</td>
              </tr>
            )}
            {rows.map((c) => (
              <tr
                key={c.id}
                onClick={() => navigate(`/cases/${c.id}`)}
                className="cursor-pointer border-b border-edge/60 last:border-0 hover:bg-panel2/60"
              >
                <td className="px-4 py-2.5 font-mono text-faint">{c.case_id}</td>
                <td className="max-w-sm truncate px-4 py-2.5 text-ink">{c.title}</td>
                <td className="px-4 py-2.5"><SeverityBadge value={c.severity} /></td>
                <td className="px-4 py-2.5"><StatusPill value={c.status} /></td>
                <td className="px-4 py-2.5 text-muted">{c.alert_count}</td>
                <td className="px-4 py-2.5 text-faint">
                  {new Date(c.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
