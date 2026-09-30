import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import { enrichmentApi } from '../api/endpoints';
import type { EnrichmentProvider, EnrichmentRow } from '../api/endpoints';
import { useAuth } from '../auth';

const VERDICT_CLS: Record<string, string> = {
  malicious: 'bg-danger/15 text-danger',
  suspicious: 'bg-warn/15 text-warn',
  clean: 'bg-ok/15 text-ok',
  unknown: 'bg-panel2 text-muted',
};

export function Enrichment() {
  const { me } = useAuth();
  const isAdmin = me?.role === 'admin';

  const [providers, setProviders] = useState<EnrichmentProvider[]>([]);
  const [rows, setRows] = useState<EnrichmentRow[]>([]);
  const [q, setQ] = useState('');
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState('');
  const [urlTemplate, setUrlTemplate] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [prov, results] = await Promise.all([
        enrichmentApi.providers(),
        enrichmentApi.results(q),
      ]);
      setProviders(prov.results);
      setRows(results.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load enrichment');
    }
  }, [q]);

  useEffect(() => {
    void load();
  }, [load]);

  const addProvider = async () => {
    if (!name.trim() || !urlTemplate.includes('{value}')) {
      setError('Name and a url_template containing {value} are required.');
      return;
    }
    setError('');
    try {
      const created = await enrichmentApi.createProvider({
        name: name.trim(),
        kind: 'http_lookup',
        config: { url_template: urlTemplate.trim() },
      });
      setProviders((prev) => [...prev, created]);
      setShowAdd(false);
      setName('');
      setUrlTemplate('');
      setNote(`Added provider “${created.name}”`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to add provider');
    }
  };

  const toggleProvider = async (p: EnrichmentProvider) => {
    try {
      const updated = await enrichmentApi.patchProvider(p.id, { enabled: !p.enabled });
      setProviders((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Update failed');
    }
  };

  const removeProvider = async (p: EnrichmentProvider) => {
    try {
      await enrichmentApi.removeProvider(p.id);
      setProviders((prev) => prev.filter((x) => x.id !== p.id));
      setNote(`Removed provider “${p.name}”`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Delete failed');
    }
  };

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-edge bg-panel">
        <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-faint">Providers</h2>
          {isAdmin && (
            <button
              type="button"
              onClick={() => setShowAdd((v) => !v)}
              className="rounded border border-edge px-2 py-1 text-xs text-muted hover:border-accent hover:text-ink"
            >
              {showAdd ? 'Cancel' : '+ Add endpoint'}
            </button>
          )}
        </div>

        {error && (
          <div className="m-3 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
            {error}
          </div>
        )}
        {note && (
          <div className="m-3 rounded-md border border-ok/40 bg-ok/10 px-3 py-2 text-xs text-ok">{note}</div>
        )}

        {showAdd && (
          <div className="space-y-2 border-b border-edge p-4">
            <div className="text-[11px] uppercase tracking-wide text-faint">
              User-owned endpoint (opt-in — nothing leaves your machine unless you add it)
            </div>
            <div className="flex gap-2">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="name (e.g. my-misp)"
                className="flex-1 rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink placeholder:text-faint focus:border-accent"
              />
              <input
                value={urlTemplate}
                onChange={(e) => setUrlTemplate(e.target.value)}
                placeholder="http://misp.local/api/search?value={value}"
                className="flex-[2] rounded-md border border-edge bg-panel2 px-3 py-1.5 font-mono text-xs text-ink placeholder:text-faint focus:border-accent"
              />
              <button
                type="button"
                onClick={() => void addProvider()}
                className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink hover:opacity-90"
              >
                Add
              </button>
            </div>
          </div>
        )}

        <table className="w-full text-left text-xs">
          <thead className="border-b border-edge text-[11px] uppercase tracking-wide text-faint">
            <tr>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Kind</th>
              <th className="px-4 py-2 font-medium">Config</th>
              <th className="px-4 py-2 font-medium">Enabled</th>
              {isAdmin && <th className="px-4 py-2 font-medium" />}
            </tr>
          </thead>
          <tbody>
            {providers.map((p) => (
              <tr key={p.id} className="border-b border-edge/60 last:border-0">
                <td className="px-4 py-2.5 font-medium text-ink">{p.name}</td>
                <td className="px-4 py-2.5 text-muted">{p.kind}</td>
                <td className="max-w-md truncate px-4 py-2.5 font-mono text-faint">
                  {String(p.config.path ?? p.config.url_template ?? '—')}
                </td>
                <td className="px-4 py-2.5">
                  <button
                    type="button"
                    onClick={() => void toggleProvider(p)}
                    disabled={!isAdmin}
                    className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                      p.enabled ? 'bg-ok/15 text-ok' : 'bg-panel2 text-faint'
                    } disabled:cursor-not-allowed`}
                    title={isAdmin ? 'Toggle provider' : 'Admin only'}
                  >
                    {p.enabled ? 'on' : 'off'}
                  </button>
                </td>
                {isAdmin && (
                  <td className="px-4 py-2.5 text-right">
                    <button
                      type="button"
                      onClick={() => void removeProvider(p)}
                      className="text-[11px] text-faint hover:text-danger"
                    >
                      delete
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="rounded-lg border border-edge bg-panel">
        <div className="flex items-center gap-3 border-b border-edge px-4 py-2.5">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-faint">Recent results</h2>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="filter by ioc or provider…"
            className="ml-auto w-64 rounded-md border border-edge bg-panel2 px-3 py-1 text-xs text-ink placeholder:text-faint focus:border-accent"
          />
        </div>
        <table className="w-full text-left text-xs">
          <thead className="border-b border-edge text-[11px] uppercase tracking-wide text-faint">
            <tr>
              <th className="px-4 py-2 font-medium">IOC</th>
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 font-medium">Provider</th>
              <th className="px-4 py-2 font-medium">Verdict</th>
              <th className="px-4 py-2 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-muted">
                  No enrichment results — run “Enrich” from a case or a playbook.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={`${r.ioc_value}-${r.provider}`} className="border-b border-edge/60 last:border-0">
                <td className="px-4 py-2.5 font-mono text-ink">{r.ioc_value}</td>
                <td className="px-4 py-2.5 text-muted">{r.ioc_type}</td>
                <td className="px-4 py-2.5 text-muted">{r.provider}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${VERDICT_CLS[r.verdict] ?? 'bg-panel2 text-muted'}`}
                  >
                    {r.verdict}
                  </span>
                </td>
                <td className="max-w-sm truncate px-4 py-2.5 font-mono text-faint">
                  {String(r.data?.note ?? '') || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
