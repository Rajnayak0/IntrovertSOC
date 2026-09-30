import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import { modelApi } from '../api/endpoints';
import type { ModelConfig } from '../api/endpoints';
import { useAuth } from '../auth';
import { useModelStatus } from '../components/ModelStatus';

export function ModelSettings() {
  const { me } = useAuth();
  const isAdmin = me?.role === 'admin';
  const { status, loading, refresh } = useModelStatus(15_000);

  const [config, setConfig] = useState<ModelConfig | null>(null);
  const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState('');
  const [ggufPath, setGgufPath] = useState('');
  const [ctxWindow, setCtxWindow] = useState('0');
  const [osTab, setOsTab] = useState<'windows' | 'posix'>('windows');
  const [flash, setFlash] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const loadConfig = useCallback(async () => {
    try {
      const c = await modelApi.config();
      setConfig(c);
      setBaseUrl(c.override.base_url);
      setModel(c.override.model);
      setGgufPath(c.override.gguf_path);
      setCtxWindow(String(c.override.context_window ?? 0));
    } catch {
      setConfig(null);
    }
  }, []);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const save = async () => {
    setSaving(true);
    setFlash(null);
    try {
      const s = await modelApi.saveConfig({
        base_url: baseUrl,
        model,
        gguf_path: ggufPath,
        context_window: Number.parseInt(ctxWindow, 10) || 0,
      });
      setFlash({ kind: 'ok', text: s.connected ? 'Saved — connection OK.' : 'Saved — server still unreachable.' });
      await loadConfig();
      await refresh(true);
    } catch (err) {
      setFlash({ kind: 'err', text: err instanceof ApiError ? err.message : 'Save failed' });
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setFlash(null);
    try {
      const s = await modelApi.test();
      setFlash(
        s.connected
          ? { kind: 'ok', text: `Connected in ${s.latency_ms ?? '?'} ms — ${s.server_model ?? s.model}` }
          : { kind: 'err', text: s.banner ?? s.detail },
      );
      await refresh(true);
    } catch (err) {
      setFlash({ kind: 'err', text: err instanceof ApiError ? err.message : 'Test failed' });
    }
  };

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setFlash({ kind: 'ok', text: 'Command copied.' });
    } catch {
      setFlash({ kind: 'err', text: 'Clipboard unavailable — select and copy manually.' });
    }
  };

  const cmd = config?.launch_commands[osTab] ?? '';
  const sourceLabel =
    status?.config_source === 'db' ? 'this page' : status?.config_source === 'env' ? '.env' : 'default';

  return (
    <div className="max-w-3xl space-y-6">
      <section className="rounded-lg border border-edge bg-panel">
        <div className="flex items-center justify-between border-b border-edge px-5 py-3">
          <div className="flex items-center gap-2.5">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                loading ? 'bg-faint' : status?.connected ? 'bg-ok' : 'bg-danger'
              }`}
            />
            <h2 className="text-sm font-semibold">
              {loading ? 'Checking…' : status?.connected ? 'Model server connected' : 'Model server not detected'}
            </h2>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void refresh(true)}
              className="rounded-md border border-edge bg-panel2 px-3 py-1.5 text-xs text-ink hover:border-accent"
            >
              Re-check
            </button>
            {isAdmin && (
              <button
                type="button"
                onClick={() => void test()}
                className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink hover:opacity-90"
              >
                Test connection
              </button>
            )}
          </div>
        </div>

        <dl className="grid grid-cols-1 gap-x-6 gap-y-3 px-5 py-4 text-sm sm:grid-cols-2">
          <Field label="Endpoint" value={status?.base_url ?? '—'} mono />
          <Field label="Configured model" value={status?.model ?? '—'} mono />
          <Field
            label="Model reported by server"
            value={status?.server_model ?? (status?.connected ? '—' : 'not connected')}
            mono
          />
          <Field label="Model family" value={status?.family ?? '—'} mono />
          <Field
            label="Context window"
            value={
              status?.context_window
                ? `${status.context_window.toLocaleString()} (${status.context_source ?? 'default'})`
                : '—'
            }
            mono
          />
          <Field
            label="Latency"
            value={status?.connected && status.latency_ms != null ? `${status.latency_ms} ms` : '—'}
          />
          <Field label="Config source" value={sourceLabel} />
          <Field
            label="Last check"
            value={status ? new Date(status.checked_at * 1000).toLocaleTimeString() : '—'}
          />
        </dl>

        {!loading && !status?.connected && (
          <div className="border-t border-edge bg-warn/10 px-5 py-3 text-xs leading-relaxed">
            <span className="font-medium text-warn">{status?.banner}</span>
            <span className="block text-muted">
              Keep the llamafile terminal open while you use AI features. Everything else — alerts,
              cases, playbooks — works without it.
            </span>
          </div>
        )}
      </section>

      <section className="rounded-lg border border-edge bg-panel">
        <div className="border-b border-edge px-5 py-3">
          <h2 className="text-sm font-semibold">Endpoint configuration</h2>
          <p className="mt-0.5 text-xs text-muted">
            Overrides .env. No API key exists for this server and none can be entered here — the
            model runs on this machine.
          </p>
        </div>

        <div className="space-y-4 px-5 py-4">
          <ConfigField
            label="Base URL"
            hint="Where llamafile listens. Default http://127.0.0.1:8080"
            value={baseUrl}
            onChange={setBaseUrl}
            disabled={!isAdmin}
            placeholder="http://127.0.0.1:8080"
          />
          <ConfigField
            label="Model name"
            hint="Cosmetic label sent with each request."
            value={model}
            onChange={setModel}
            disabled={!isAdmin}
            placeholder="local-model"
          />
          <ConfigField
            label="GGUF model file"
            hint="Path to the weights file you launch llamafile with (used to generate the command below)."
            value={ggufPath}
            onChange={setGgufPath}
            disabled={!isAdmin}
            placeholder="C:\models\Qwen3-4B-Q4_K_M.gguf"
          />
          <ConfigField
            label="Context window (tokens)"
            hint="0 = auto (server-reported, else 32768). At 128k+ the whole knowledge base is sent inline instead of top-K search."
            value={ctxWindow}
            onChange={setCtxWindow}
            disabled={!isAdmin}
            placeholder="0"
          />

          {flash && (
            <div
              className={`rounded-md border px-3 py-2 text-xs ${
                flash.kind === 'ok'
                  ? 'border-ok/40 bg-ok/10 text-ok'
                  : 'border-danger/40 bg-danger/10 text-danger'
              }`}
            >
              {flash.text}
            </div>
          )}

          {isAdmin ? (
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setBaseUrl(config?.override.base_url ?? '');
                  setModel(config?.override.model ?? '');
                  setGgufPath(config?.override.gguf_path ?? '');
                  setCtxWindow(String(config?.override.context_window ?? 0));
                  setFlash(null);
                }}
                className="rounded-md border border-edge px-3 py-1.5 text-xs text-muted hover:text-ink"
              >
                Reset
              </button>
              <button
                type="button"
                onClick={() => void save()}
                disabled={saving}
                className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink hover:opacity-90 disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save & re-test'}
              </button>
            </div>
          ) : (
            <p className="text-right text-xs text-faint">Only admins can edit the endpoint.</p>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-edge bg-panel">
        <div className="flex items-center justify-between border-b border-edge px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold">Start / switch the local model</h2>
            <p className="mt-0.5 text-xs text-muted">
              llamafile loads the GGUF at startup — run this after changing the model file.
            </p>
          </div>
          <div className="flex rounded-md border border-edge bg-panel2 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setOsTab('windows')}
              className={`rounded px-2.5 py-1 ${osTab === 'windows' ? 'bg-accent text-accent-ink' : 'text-muted'}`}
            >
              Windows
            </button>
            <button
              type="button"
              onClick={() => setOsTab('posix')}
              className={`rounded px-2.5 py-1 ${osTab === 'posix' ? 'bg-accent text-accent-ink' : 'text-muted'}`}
            >
              macOS / Linux
            </button>
          </div>
        </div>
        <div className="px-5 py-4">
          <div className="flex items-start gap-3 rounded-md border border-edge bg-surface p-3">
            <code className="min-w-0 flex-1 overflow-x-auto whitespace-pre font-mono text-xs text-ink">
              {cmd || '—'}
            </code>
            <button
              type="button"
              onClick={() => void copy(cmd)}
              className="shrink-0 rounded border border-edge bg-panel px-2 py-1 text-xs text-muted hover:border-accent hover:text-ink"
            >
              Copy
            </button>
          </div>
          <p className="mt-2 text-xs text-faint">{config?.launch_commands.note}</p>
        </div>
      </section>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-faint">{label}</dt>
      <dd className={`mt-0.5 truncate text-sm text-ink ${mono ? 'font-mono' : ''}`} title={value}>
        {value}
      </dd>
    </div>
  );
}

function ConfigField({
  label,
  hint,
  value,
  onChange,
  disabled,
  placeholder,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
  placeholder: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-muted">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        className="w-full rounded-md border border-edge bg-panel2 px-3 py-2 font-mono text-xs text-ink placeholder:text-faint focus:border-accent disabled:opacity-60"
      />
      <p className="mt-1 text-[11px] text-faint">{hint}</p>
    </div>
  );
}
