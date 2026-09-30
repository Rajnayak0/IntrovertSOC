import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '../api/client';
import { casesApi, playbooksApi } from '../api/endpoints';
import type { CaseRow, Playbook, PlaybookRun, RunStep } from '../api/endpoints';
import { useAuth } from '../auth';

const RUN_POLL_MS = 1200;
const TERMINAL = new Set(['succeeded', 'degraded', 'failed']);
const RUN_CLS: Record<string, string> = {
  pending: 'bg-panel2 text-faint',
  running: 'bg-accent/15 text-accent',
  succeeded: 'bg-ok/15 text-ok',
  degraded: 'bg-warn/15 text-warn',
  failed: 'bg-danger/15 text-danger',
};

export function Playbooks() {
  const { me } = useAuth();
  const isAdmin = me?.role === 'admin';

  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [runs, setRuns] = useState<PlaybookRun[]>([]);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [caseId, setCaseId] = useState<number | ''>('');
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [runningId, setRunningId] = useState<number | null>(null);
  const [editing, setEditing] = useState<Playbook | null>(null);
  const [editText, setEditText] = useState('');
  const [saving, setSaving] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    setError('');
    try {
      const [pb, runPage, casePage] = await Promise.all([
        playbooksApi.list(),
        playbooksApi.runs({ limit: '15' }),
        casesApi.list({ limit: '100' }),
      ]);
      setPlaybooks(pb.results);
      setRuns(runPage.results);
      setCases(casePage.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load playbooks');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => () => {
    if (pollRef.current) clearTimeout(pollRef.current);
  }, []);

  const pollRun = useCallback(
    async (runId: number) => {
      try {
        const run = await playbooksApi.runDetail(runId);
        setRuns((prev) => [run, ...prev.filter((r) => r.id !== run.id)]);
        if (TERMINAL.has(run.status)) {
          setRunningId(null);
          setNote(
            run.status === 'succeeded'
              ? `Run #${run.id} finished (${run.mode} mode)`
              : run.status === 'degraded'
                ? `Run #${run.id} finished with step errors`
                : `Run #${run.id} failed: ${run.error}`,
          );
        } else {
          pollRef.current = setTimeout(() => void pollRun(runId), RUN_POLL_MS);
        }
      } catch (err) {
        setRunningId(null);
        setError(err instanceof ApiError ? err.message : 'Polling failed');
      }
    },
    [],
  );

  const startRun = async (pb: Playbook) => {
    setError('');
    setNote('');
    setRunningId(pb.id);
    try {
      const run = await playbooksApi.run(pb.id, caseId || null);
      setRuns((prev) => [run, ...prev.filter((r) => r.id !== run.id)]);
      await pollRun(run.id);
    } catch (err) {
      setRunningId(null);
      setError(err instanceof ApiError ? err.message : 'Run failed to start');
    }
  };

  const saveDefinition = async () => {
    if (!editing) return;
    setSaving(true);
    setError('');
    try {
      const updated = await playbooksApi.save(editing.id, editText);
      setPlaybooks((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setEditing(null);
      setNote(`Saved ${updated.name}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const needsCase = (steps: string[]) => steps.some((s) => s !== 'log');

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-muted">
          Case context{' '}
          <select
            value={caseId}
            onChange={(e) => setCaseId(e.target.value ? Number(e.target.value) : '')}
            className="ml-1 rounded-md border border-edge bg-panel2 px-2 py-1.5 text-xs text-ink"
          >
            <option value="">— none —</option>
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.case_id} · {c.title}
              </option>
            ))}
          </select>
        </label>
        <span className="text-[11px] text-faint">steps run in order; LLM steps use your chat mode</span>
        <span className="ml-auto text-xs text-faint">{playbooks.length} playbook(s)</span>
      </div>

      {error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>
      )}
      {note && (
        <div className="rounded-md border border-ok/40 bg-ok/10 px-3 py-2 text-xs text-ok">{note}</div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {playbooks.map((pb) => (
          <div key={pb.id} className="rounded-lg border border-edge bg-panel">
            <div className="flex items-start justify-between gap-2 border-b border-edge px-4 py-2.5">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-ink">{pb.name}</span>
                  {pb.builtin && (
                    <span className="rounded bg-panel2 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-faint">
                      builtin
                    </span>
                  )}
                  {!pb.enabled && (
                    <span className="rounded bg-danger/15 px-1.5 py-0.5 text-[10px] text-danger">disabled</span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-muted">{pb.description}</p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {pb.steps_preview.map((s, i) => (
                    <span key={i} className="rounded bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] text-accent">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex shrink-0 gap-1.5">
                {isAdmin && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(pb);
                      setEditText(pb.definition);
                    }}
                    className="rounded border border-edge px-2 py-1 text-xs text-muted hover:border-accent hover:text-ink"
                  >
                    YAML
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void startRun(pb)}
                  disabled={runningId !== null || !pb.enabled}
                  className="rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
                >
                  {runningId === pb.id ? 'Running…' : 'Run'}
                </button>
              </div>
            </div>
            {needsCase(pb.steps_preview) && (
              <div className="px-4 py-2 text-[11px] text-faint">
                needs a case
                {!caseId && ' — pick one above before running'}
              </div>
            )}
          </div>
        ))}
      </div>

      {editing && (
        <div className="rounded-lg border border-edge bg-panel">
          <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-faint">
              Edit YAML · {editing.name}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setEditing(null)}
                className="rounded border border-edge px-2 py-1 text-xs text-muted hover:text-ink"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void saveDefinition()}
                disabled={saving}
                className="rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            spellCheck={false}
            className="h-64 w-full bg-panel2 p-4 font-mono text-xs leading-relaxed text-ink outline-none"
          />
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-edge bg-panel">
        <div className="border-b border-edge px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-faint">
          Recent runs
        </div>
        <table className="w-full text-left text-xs">
          <tbody>
            {runs.length === 0 && (
              <tr>
                <td className="px-4 py-5 text-center text-muted">No runs yet.</td>
              </tr>
            )}
            {runs.map((run) => (
              <tr key={run.id} className="border-b border-edge/60 last:border-0 align-top">
                <td className="whitespace-nowrap px-4 py-2.5 text-faint">{new Date(run.created_at).toLocaleString()}</td>
                <td className="px-4 py-2.5 font-medium text-ink">{run.playbook}</td>
                <td className="px-4 py-2.5 text-muted">{run.case ?? '—'}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${RUN_CLS[run.status] ?? 'bg-panel2 text-muted'}`}
                  >
                    {run.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-[11px] text-muted">
                  {run.steps.length === 0 && '—'}
                  <ul className="space-y-0.5">
                    {run.steps.map((s: RunStep) => (
                      <li key={s.index} className="font-mono">
                        <span className={s.status === 'ok' ? 'text-ok' : 'text-danger'}>
                          {s.status === 'ok' ? '✓' : '✗'}
                        </span>{' '}
                        {s.type} <span className="text-faint">{s.ms}ms</span>
                        <div className="pl-4 text-faint">{s.detail}</div>
                      </li>
                    ))}
                  </ul>
                </td>
                <td className="px-4 py-2.5 text-[11px] text-faint">{run.mode}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
