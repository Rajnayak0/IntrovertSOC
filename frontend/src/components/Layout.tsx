import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../auth';
import { useTheme } from '../theme';
import { ModeSwitcher } from './ModeSwitcher';
import { StatusDot, useModelStatus } from './ModelStatus';

type IconName =
  | 'dashboard'
  | 'alerts'
  | 'cases'
  | 'playbooks'
  | 'knowledge'
  | 'enrichment'
  | 'settings'
  | 'audit'
  | 'sun'
  | 'moon';

const PATHS: Record<IconName, string> = {
  dashboard: 'M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z',
  alerts: 'M12 3a6 6 0 0 0-6 6v3l-2 4h16l-2-4V9a6 6 0 0 0-6-6zM10 20a2 2 0 0 0 4 0',
  cases: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  playbooks: 'M6 4l14 8-14 8z',
  knowledge: 'M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM8 20a3 3 0 0 1 0-6h11',
  enrichment: 'M12 3v6m0 6v6M5.6 7.5l5.2 3M13.2 13.5l5.2 3M5.6 16.5l5.2-3M13.2 10.5l5.2-3',
  settings:
    'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19 12a7 7 0 0 1-.1 1l2 1.5-2 3.4-2.3-.8a7 7 0 0 1-1.7 1l-.4 2.4h-4l-.4-2.4a7 7 0 0 1-1.7-1l-2.3.8-2-3.4 2-1.5a7 7 0 0 1 0-2l-2-1.5 2-3.4 2.3.8a7 7 0 0 1 1.7-1L10.5 2h4l.4 2.4a7 7 0 0 1 1.7 1l2.3-.8 2 3.4-2 1.5a7 7 0 0 1 .1 1z',
  audit: 'M6 3h9l4 4v14H6zM14 3v5h5M9 13h6M9 17h6',
  sun: 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z',
};

export function Icon({ name, className = 'h-4 w-4' }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className={className}>
      <path d={PATHS[name]} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: '/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/alerts', label: 'Alerts', icon: 'alerts' },
  { to: '/cases', label: 'Cases', icon: 'cases' },
  { to: '/playbooks', label: 'Playbooks', icon: 'playbooks' },
  { to: '/knowledge', label: 'Knowledge Base', icon: 'knowledge' },
  { to: '/enrichment', label: 'Enrichment', icon: 'enrichment' },
  { to: '/model', label: 'Model Settings', icon: 'settings' },
  { to: '/audit', label: 'Audit Log', icon: 'audit' },
];

const TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/alerts': 'Alerts',
  '/cases': 'Cases',
  '/playbooks': 'Playbooks',
  '/knowledge': 'Knowledge Base',
  '/enrichment': 'Enrichment',
  '/model': 'Model Settings',
  '/audit': 'Audit Log',
};

export function Layout() {
  const { me, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const { status, refresh } = useModelStatus();
  const location = useLocation();
  const title = TITLES[location.pathname]
    ?? (location.pathname.startsWith('/cases/') ? 'Case detail' : '');

  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r border-edge bg-panel">
        <div className="flex items-center gap-2.5 px-4 py-4">
          <span className="flex h-7 w-7 items-center justify-center rounded bg-accent font-mono text-xs font-bold text-accent-ink">
            &gt;_
          </span>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-tight">IntrovertSOC</div>
            <div className="text-[10px] uppercase tracking-widest text-faint">offline · local</div>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 px-2 py-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-panel2 text-ink shadow-[inset_2px_0_0_var(--accent)]'
                    : 'text-muted hover:bg-panel2 hover:text-ink'
                }`
              }
            >
              <Icon name={item.icon} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-edge px-4 py-3 text-[11px] leading-relaxed text-faint">
          No telemetry. No cloud AI.
          <br />
          Traffic: local model + your sources only.
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-3 border-b border-edge bg-panel px-4">
          <h1 className="flex-1 truncate text-sm font-medium text-muted">{title}</h1>

          <ModeSwitcher />

          <span
            className="flex items-center gap-1.5 text-xs text-muted"
            title={status?.detail ?? 'Checking model server…'}
          >
            <StatusDot status={status} />
            <span className="hidden md:inline">{status?.connected ? 'model online' : 'model offline'}</span>
          </span>

          <button
            type="button"
            onClick={toggle}
            className="rounded-md p-1.5 text-muted hover:bg-panel2 hover:text-ink"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label="Toggle theme"
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} className="h-4 w-4" />
          </button>

          <div className="flex items-center gap-2 border-l border-edge pl-3">
            <span className="text-xs text-muted" title={me?.role}>
              {me?.username}
            </span>
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded-md px-2 py-1 text-xs text-muted hover:bg-panel2 hover:text-ink"
            >
              Sign out
            </button>
          </div>
        </header>

        {status && !status.connected && status.banner && (
          <div className="flex items-center gap-3 border-b border-edge bg-warn/10 px-4 py-2 text-xs text-warn">
            <span className="font-medium">Model offline</span>
            <span className="flex-1 text-muted">{status.banner}</span>
            <button
              type="button"
              onClick={() => void refresh(true)}
              className="rounded border border-edge bg-panel px-2 py-0.5 text-xs text-ink hover:border-accent"
            >
              Retry
            </button>
          </div>
        )}

        <main className="min-h-0 flex-1 overflow-y-auto">
          <div key={location.pathname} className="animate-in p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
