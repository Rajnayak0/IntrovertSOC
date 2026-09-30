import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { useAuth } from '../auth';

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-full items-center justify-center p-6">
      <div className="w-full max-w-sm animate-in">
        <div className="mb-6 flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded bg-accent font-mono text-sm font-bold text-accent-ink">
            &gt;_
          </span>
          <div>
            <div className="text-lg font-semibold tracking-tight">IntrovertSOC</div>
            <div className="text-xs text-muted">Offline security operations console</div>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4 rounded-lg border border-edge bg-panel p-5">
          <div>
            <label htmlFor="username" className="mb-1 block text-xs font-medium text-muted">
              Username
            </label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              className="w-full rounded-md border border-edge bg-panel2 px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-accent"
              placeholder="analyst"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-xs font-medium text-muted">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="w-full rounded-md border border-edge bg-panel2 px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-accent"
              placeholder="••••••••"
            />
          </div>

          {error && <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>}

          <button
            type="submit"
            disabled={busy || !username || !password}
            className="w-full rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-ink transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="text-center text-[11px] text-faint">
            Local accounts only — no SSO, no external auth.
          </p>
        </form>
      </div>
    </div>
  );
}
