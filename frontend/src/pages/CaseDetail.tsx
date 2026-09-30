import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import { alertsApi, casesApi } from '../api/endpoints';
import type { Alert, CaseDetail } from '../api/endpoints';
import { useAuth } from '../auth';
import { SeverityBadge, StatusPill } from '../components/badges';

const CASE_STATUSES = ['New', 'In Progress', 'On Hold', 'Resolved', 'Closed'];

const EVENT_KIND_CLS: Record<string, string> = {
  status: 'text-warn',
  link: 'text-accent',
  comment: 'text-ink',
  system: 'text-faint',
};

type AiReport = {
  summary?: string;
  report_md?: string;
  assessment?: { rationale?: string; next_steps?: string[]; confidence?: string };
  mode?: string;
  model?: string;
  degraded?: string[];
  created_at?: string;
};

const MODE_LABELS: Record<string, string> = {
  work: 'Work',
  introvert: 'Introvert',
  super_introvert: 'Super Introvert',
  paranoid: 'Paranoid',
  zen: 'Zen',
};

type ChatMsg = { role: 'user' | 'assistant'; content: string };

export function CaseDetailPage() {
  const { id } = useParams();
  const caseId = Number(id);
  const { me } = useAuth();
  const canEdit = me?.role !== 'viewer';

  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [orphans, setOrphans] = useState<Alert[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [investigating, setInvestigating] = useState(false);
  const [investNote, setInvestNote] = useState('');
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);

  const load = useCallback(async () => {
    setError('');
    try {
      setDetail(await casesApi.detail(caseId));
      if (canEdit) {
        const page = await alertsApi.list({ orphan: '1', limit: '50' });
        setOrphans(page.results);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load case');
    }
  }, [caseId, canEdit]);

  useEffect(() => {
    void load();
  }, [load]);

  const setStatus = async (next: string) => {
    if (!detail) return;
    setBusy(true);
    try {
      setDetail(await casesApi.patch(detail.id, { status: next }));
      void load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Update failed');
    } finally {
      setBusy(false);
    }
  };

  const link = async (alertId: number) => {
    if (!detail) return;
    setBusy(true);
    try {
      await casesApi.linkAlerts(detail.id, [alertId]);
      void load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Link failed');
    } finally {
      setBusy(false);
    }
  };

  const runInvestigation = async () => {
    if (!detail) return;
    setInvestigating(true);
    setError('');
    setInvestNote('');
    try {
      const res = await casesApi.investigate(detail.id);
      setDetail(res.case);
      setInvestNote(
        `Investigation finished in ${(res.ms / 1000).toFixed(1)}s (mode: ${res.mode})` +
          (res.degraded.length ? ` — degraded nodes: ${res.degraded.join(', ')}` : ''),
      );
      void load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Investigation failed');
    } finally {
      setInvestigating(false);
    }
  };

  const ask = async () => {
    const q = question.trim();
    if (!q || asking || !detail) return;
    setAsking(true);
    setError('');
    setQuestion('');
    try {
      const res = await casesApi.ask(detail.id, q, chat);
      setChat((c) => [...c, { role: 'user', content: q }, { role: 'assistant', content: res.answer }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Ask failed');
      setQuestion(q);
    } finally {
      setAsking(false);
    }
  };

  if (!detail && !error) {
    return <div className="text-sm text-muted">Loading…</div>;
  }
  if (!detail) {
    return (
      <div className="space-y-3">
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>
        <Link to="/cases" className="text-xs text-accent">← Back to cases</Link>
      </div>
    );
  }

  const report: AiReport | null = detail.investigation_report_ai_json
    ? (() => {
        try {
          return JSON.parse(detail.investigation_report_ai_json) as AiReport;
        } catch {
          return null;
        }
      })()
    : null;
  const hasAi = Boolean(detail.severity_ai || report);
  const nextSteps = report?.assessment?.next_steps ?? [];

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex items-center gap-3 text-xs text-muted">
        <Link to="/cases" className="hover:text-ink">← Cases</Link>
        <span className="font-mono text-faint">{detail.case_id}</span>
        {investNote && <span className="text-ok">{investNote}</span>}
      </div>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-ink">{detail.title}</h2>
          <div className="mt-2 flex items-center gap-2">
            <SeverityBadge value={detail.severity || 'Unknown'} />
            <StatusPill value={detail.status} />
            {detail.assignee && <span className="text-xs text-muted">→ {detail.assignee}</span>}
            <span className="text-xs text-faint">{new Date(detail.created_at).toLocaleString()}</span>
          </div>
        </div>
        {canEdit && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void runInvestigation()}
              disabled={busy || investigating}
              className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
              title="Run the local model over this case (4 short LLM calls)"
            >
              {investigating ? 'Investigating…' : 'Run investigation'}
            </button>
            <select
              value={detail.status}
              disabled={busy || investigating}
              onChange={(e) => void setStatus(e.target.value)}
              className="rounded-md border border-edge bg-panel2 px-2 py-1.5 text-xs text-ink disabled:opacity-50"
            >
              {CASE_STATUSES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>
      )}

      <section className="rounded-lg border border-edge bg-panel">
        <div className="border-b border-edge px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-faint">
          Linked alerts ({detail.alerts.length})
        </div>
        {detail.alerts.length === 0 ? (
          <div className="px-4 py-4 text-xs text-muted">No alerts linked yet.</div>
        ) : (
          <ul className="divide-y divide-edge/60">
            {detail.alerts.map((a) => (
              <li key={a.id} className="flex items-center gap-3 px-4 py-2.5 text-xs">
                <span className="font-mono text-faint">{a.alert_id}</span>
                <SeverityBadge value={a.severity} />
                <span className="flex-1 truncate text-ink">{a.title}</span>
                <StatusPill value={a.status} />
              </li>
            ))}
          </ul>
        )}
        {canEdit && orphans.length > 0 && (
          <div className="border-t border-edge px-4 py-3">
            <div className="mb-2 text-[11px] uppercase tracking-wide text-faint">Attach an unassigned alert</div>
            <div className="flex flex-wrap gap-2">
              {orphans.slice(0, 10).map((a) => (
                <button
                  key={a.id}
                  type="button"
                  disabled={busy}
                  onClick={() => void link(a.id)}
                  title={a.title}
                  className="max-w-64 truncate rounded-md border border-edge bg-panel2 px-2 py-1 text-[11px] text-muted hover:border-accent hover:text-ink disabled:opacity-50"
                >
                  {a.alert_id} · {a.title}
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      {hasAi && (
        <section className="rounded-lg border border-edge bg-panel">
          <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-faint">AI assessment</h2>
            <span className="text-[11px] text-faint">
              {report?.mode ? `mode: ${report.mode}` : ''}
              {report?.model ? ` · ${report.model}` : ''}
            </span>
          </div>
          <div className="space-y-3 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              {detail.severity_ai && <SeverityBadge value={detail.severity_ai} />}
              {detail.verdict_ai && (
                <span className="rounded bg-panel2 px-1.5 py-0.5 text-[11px] font-medium text-muted">
                  {detail.verdict_ai}
                </span>
              )}
              {detail.confidence_ai && (
                <span className="rounded bg-panel2 px-1.5 py-0.5 text-[11px] text-muted">
                  confidence: {detail.confidence_ai}
                </span>
              )}
            </div>
            {report?.summary && (
              <p className="whitespace-pre-wrap text-xs leading-relaxed text-muted">{report.summary}</p>
            )}
            {report?.assessment?.rationale && (
              <p className="text-xs leading-relaxed text-ink">{report.assessment.rationale}</p>
            )}
            {nextSteps.length > 0 && (
              <div>
                <div className="mb-1 text-[11px] uppercase tracking-wide text-faint">Recommended actions</div>
                <ul className="list-inside list-disc space-y-0.5 text-xs text-muted">
                  {nextSteps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
            {report?.degraded && report.degraded.length > 0 && (
              <div className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
                Partial run — degraded nodes: {report.degraded.join(', ')}
              </div>
            )}
            {report?.report_md && (
              <details className="text-xs">
                <summary className="cursor-pointer text-accent hover:underline">Full report</summary>
                <pre className="mt-2 whitespace-pre-wrap rounded-md border border-edge bg-surface p-3 leading-relaxed text-muted">
                  {report.report_md}
                </pre>
              </details>
            )}
          </div>
        </section>
      )}

      <section className="rounded-lg border border-edge bg-panel">
        <div className="border-b border-edge px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-faint">
          Timeline
        </div>
        <ul className="divide-y divide-edge/60">
          {detail.events.map((e) => (
            <li key={e.id} className="flex items-baseline gap-3 px-4 py-2.5 text-xs">
              <span className="w-24 shrink-0 text-faint">{new Date(e.created_at).toLocaleTimeString()}</span>
              <span className={`w-16 shrink-0 font-medium ${EVENT_KIND_CLS[e.kind] ?? 'text-muted'}`}>
                {e.kind}
              </span>
              <span className="flex-1 text-ink">{e.message}</span>
              {e.actor && <span className="text-faint">{e.actor}</span>}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-edge bg-panel">
        <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-faint">Ask the agent</h2>
          <span className="text-[11px] text-faint">
            answers in {MODE_LABELS[me?.chat_mode ?? 'work'] ?? me?.chat_mode} mode — switch in the top bar
          </span>
        </div>
        <div className="max-h-72 space-y-2 overflow-y-auto px-4 py-3">
          {chat.length === 0 && (
            <p className="text-xs text-muted">
              Ask anything about this case — e.g. “most likely initial access vector?” or “what's still missing?”.
            </p>
          )}
          {chat.map((m, i) => (
            <div
              key={i}
              className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-xs leading-relaxed ${
                m.role === 'user'
                  ? 'ml-auto bg-accent/15 text-ink'
                  : 'bg-panel2 text-muted'
              }`}
            >
              {m.content}
            </div>
          ))}
          {asking && <div className="text-xs text-faint">Thinking…</div>}
        </div>
        <div className="flex items-center gap-2 border-t border-edge px-4 py-3">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void ask()}
            placeholder="Ask about this case…"
            disabled={asking}
            className="flex-1 rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink placeholder:text-faint focus:border-accent disabled:opacity-60"
          />
          <button
            type="button"
            onClick={() => void ask()}
            disabled={asking || !question.trim()}
            className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
          >
            {asking ? 'Asking…' : 'Ask'}
          </button>
        </div>
      </section>

      {detail.description && (
        <section className="rounded-lg border border-edge bg-panel px-4 py-3 text-xs leading-relaxed text-muted">
          {detail.description}
        </section>
      )}
    </div>
  );
}
