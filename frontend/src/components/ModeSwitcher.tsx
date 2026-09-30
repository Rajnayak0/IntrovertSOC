import { useEffect, useState } from 'react';

import { authApi } from '../api/endpoints';
import type { ModeInfo } from '../api/endpoints';
import { useAuth } from '../auth';

const FALLBACK_MODES: ModeInfo[] = [
  {
    id: 'work',
    label: 'Work Mode',
    short: 'Work',
    description: 'Full professional detail - reasoning, context, and clear next steps.',
  },
  {
    id: 'introvert',
    label: 'Introvert Mode',
    short: 'Introvert',
    description: 'Verdict, key evidence, 1-2 recommended actions. Bullets, no small talk.',
  },
  {
    id: 'super_introvert',
    label: 'Super Introvert Mode',
    short: 'Super',
    description: 'Minimal words. STATUS / SEVERITY / ACTION only. Expands only when you ask why.',
  },
  {
    id: 'paranoid',
    label: 'Paranoid Mode',
    short: 'Paranoid',
    description: 'Assume-breach posture. Hypothesis enumeration, verification before remediation.',
  },
  {
    id: 'zen',
    label: 'Zen Mode',
    short: 'Zen',
    description: 'One calm paragraph: verdict, key reason, one action. Compact UI density.',
  },
];

export function ModeSwitcher() {
  const { me, setChatMode } = useAuth();
  const [modes, setModes] = useState<ModeInfo[]>(FALLBACK_MODES);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    authApi
      .modes()
      .then((r) => setModes(r.modes))
      .catch(() => setModes(FALLBACK_MODES));
  }, []);

  if (!me) return null;
  const active = me.chat_mode;

  const select = async (mode: string) => {
    if (mode === active || busy) return;
    setBusy(true);
    try {
      await setChatMode(mode);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="flex items-center rounded-md border border-edge bg-panel2 p-0.5"
      role="radiogroup"
      aria-label="Agent communication mode"
    >
      {modes.map((m) => {
        const isActive = m.id === active;
        return (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={isActive}
            title={`${m.label}: ${m.description}`}
            onClick={() => void select(m.id)}
            disabled={busy}
            className={`rounded px-2.5 py-1 text-xs transition-colors ${
              isActive
                ? 'bg-accent text-accent-ink'
                : 'text-muted hover:text-ink disabled:opacity-50'
            }`}
          >
            {m.short}
          </button>
        );
      })}
    </div>
  );
}
