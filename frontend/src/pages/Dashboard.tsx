import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { dashboardApi } from '../api/endpoints';
import type { DashboardStats } from '../api/endpoints';
import { StatusDot, useModelStatus } from '../components/ModelStatus';
import { SeverityBadge, StatusPill } from '../components/badges';

const SEVERITY_ORDER = ['Critical', 'High', 'Medium', 'Low', 'Informational', 'Unknown', ''];

export function Dashboard() {
  const navigate = useNavigate();
  const { status: model, loading: modelLoading, refresh } = useModelStatus(15_000);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      setStats(await dashboardApi.stats());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load dashboard');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-5">
      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Alerts (24h)"
          value={stats ? String(stats.alerts.last_24h) : '—'}
          sub={stats ? `${stats.alerts.total} total` : ''}
        />
        <StatCard
          label="Unassigned alerts"
          value={stats ? String(stats.alerts.unassigned) : '—'}
          sub="not yet linked to a case"
          tone={stats && stats.alerts.unassigned > 0 ? 'warn' : undefined}
        />
        <StatCard
          label="Open cases"
          value={stats ? String(stats.cases.open) : '—'}
          sub={stats ? `${stats.cases.total} total` : ''}
        />
        <div className="rounded-lg border border-edge bg-panel p-4">
          <div className="text-[11px] uppercase tracking-wide text-faint">Local model</div>
          <div className="mt-1.5 flex items-center gap-2">
            <StatusDot status={model} />
            <span className="text-xl font-semibold tracking-tight">
              {modelLoading ? '…' : model?.connected ? 'Online' : 'Offline'}
            </span>
          </div>
          <div className="mt-1 truncate text-xs text-muted" title={model?.detail}>
            {model?.connected
              ? `${model.server_model ?? model.model} · ${model.latency_ms ?? '?'} ms`
              : model?.banner ?? 'Checking…'}
          </div>
          <div className="mt-2 flex items-center gap-3 text-xs">
            <Link to="/model" className="text-accent hover:underline">Model settings</Link>
            <button
              type="button"
              onClick={() => void refresh(true)}
              className="text-muted hover:text-ink"
            >
              Re-check
            </button>
          </div>
        </div>
      </div>

      {stats && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] uppercase tracking-wide text-faint">Severity mix</span>
          {SEVERITY_ORDER.filter((s) => (stats.alerts.by_severity[s] ?? 0) > 0).map((s) => (
            <span
              key={s || 'none'}
              className="flex items-center gap-1.5 rounded-md border border-edge bg-panel px-2 py-1 text-xs"
            >
              <SeverityBadge value={s || 'Unknown'} />
              <span className="font-mono text-muted">{stats.alerts.by_severity[s]}</span>
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section className="rounded-lg border border-edge bg-panel">
          <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-faint">Recent alerts</h2>
            <Link to="/alerts" className="text-xs text-accent hover:underline">View all</Link>
          </div>
          {!stats || stats.recent_alerts.length === 0 ? (
            <div className="px-4 py-6 text-xs text-muted">No alerts yet.</div>
          ) : (
            <ul className="divide-y divide-edge/60">
              {stats.recent_alerts.map((a) => (
                <li key={a.id} className="flex items-center gap-3 px-4 py-2.5 text-xs">
                  <SeverityBadge value={a.severity} />
                  <span className="flex-1 truncate text-ink" title={a.title}>{a.title}</span>
                  <span className="font-mono text-faint">{a.correlation_uid || a.alert_id}</span>
                  <span className="w-20 shrink-0 text-right text-faint">
                    {new Date(a.created_at).toLocaleTimeString()}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-lg border border-edge bg-panel">
          <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-faint">Recent cases</h2>
            <Link to="/cases" className="text-xs text-accent hover:underline">View all</Link>
          </div>
          {!stats || stats.recent_cases.length === 0 ? (
            <div className="px-4 py-6 text-xs text-muted">No cases yet.</div>
          ) : (
            <ul className="divide-y divide-edge/60">
              {stats.recent_cases.map((c) => (
                <li
                  key={c.id}
                  onClick={() => navigate(`/cases/${c.id}`)}
                  className="flex cursor-pointer items-center gap-3 px-4 py-2.5 text-xs hover:bg-panel2/60"
                >
                  <span className="font-mono text-faint">{c.case_id}</span>
                  <span className="flex-1 truncate text-ink">{c.title}</span>
                  <span className="text-muted">{c.alert_count} alert(s)</span>
                  <StatusPill value={c.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub: string;
  tone?: 'warn';
}) {
  return (
    <div className="rounded-lg border border-edge bg-panel p-4">
      <div className="text-[11px] uppercase tracking-wide text-faint">{label}</div>
      <div
        className={`mt-1.5 text-2xl font-semibold tracking-tight ${
          tone === 'warn' ? 'text-warn' : 'text-ink'
        }`}
      >
        {value}
      </div>
      <div className="mt-1 truncate text-xs text-muted">{sub}</div>
    </div>
  );
}
