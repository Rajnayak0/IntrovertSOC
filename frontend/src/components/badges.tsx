const SEVERITY_CLS: Record<string, string> = {
  Critical: 'bg-danger/15 text-danger',
  High: 'bg-warn/15 text-warn',
  Medium: 'bg-warn/10 text-warn/90',
  Low: 'bg-accent/15 text-accent',
  Informational: 'bg-panel2 text-muted',
  Unknown: 'bg-panel2 text-faint',
};

export function SeverityBadge({ value }: { value: string }) {
  const cls = SEVERITY_CLS[value] ?? 'bg-panel2 text-muted';
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${cls}`}>
      {value || '—'}
    </span>
  );
}

const STATUS_CLS: Record<string, string> = {
  New: 'bg-accent/15 text-accent',
  'In Progress': 'bg-warn/15 text-warn',
  'On Hold': 'bg-panel2 text-muted',
  Resolved: 'bg-ok/15 text-ok',
  Closed: 'bg-panel2 text-faint',
  Suppressed: 'bg-panel2 text-faint',
};

export function StatusPill({ value }: { value: string }) {
  const cls = STATUS_CLS[value] ?? 'bg-panel2 text-muted';
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${cls}`}>
      {value}
    </span>
  );
}
