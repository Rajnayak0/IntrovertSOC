import { api } from './client';

export type Me = {
  id: number;
  username: string;
  role: 'admin' | 'analyst' | 'viewer';
  chat_mode: 'work' | 'introvert' | 'super_introvert' | 'paranoid' | 'zen';
  is_superuser: boolean;
};

export type ModeInfo = {
  id: string;
  label: string;
  short: string;
  description: string;
};

export type ModelStatus = {
  connected: boolean;
  base_url: string;
  model: string;
  gguf_path?: string;
  config_source?: string;
  server_model?: string | null;
  family?: string;
  context_window?: number;
  context_source?: string;
  detail: string;
  latency_ms?: number | null;
  checked_at: number;
  banner?: string;
};

export type ModelConfig = {
  effective: { base_url: string; model: string; gguf_path: string; context_window?: number };
  source: string;
  override: { base_url: string; model: string; gguf_path: string; context_window?: number };
  launch_commands: { windows: string; posix: string; note: string };
};

export const authApi = {
  me: () => api<Me>('/api/auth/me/'),
  login: (username: string, password: string) =>
    api<Me>('/api/auth/login/', { method: 'POST', body: { username, password } }),
  logout: () => api('/api/auth/logout/', { method: 'POST' }),
  setChatMode: (chat_mode: string) =>
    api<Me>('/api/auth/me/preferences/', { method: 'PUT', body: { chat_mode } }),
  modes: () => api<{ modes: ModeInfo[]; default: string }>('/api/auth/modes/'),
};

export const modelApi = {
  status: (force = false) => api<ModelStatus>(`/api/model/status/?force=${force ? '1' : '0'}`),
  test: () => api<ModelStatus>('/api/model/test/', { method: 'POST' }),
  config: () => api<ModelConfig>('/api/model/config/'),
  saveConfig: (body: {
    base_url: string;
    model: string;
    gguf_path: string;
    context_window: number;
  }) => api<ModelStatus>('/api/model/config/', { method: 'PUT', body }),
};

export type Page<T> = { count: number; results: T[] };

export type Alert = {
  id: number;
  alert_id: string;
  title: string;
  desc: string;
  severity: string;
  status: string;
  source: string;
  rule_id: string;
  rule_name: string;
  correlation_uid: string;
  tactic: string;
  labels: string[];
  case: number | null;
  case_id_ref: { id: number; case_id: string; title: string } | null;
  created_at: string;
};

export type CaseStatusValue = 'New' | 'In Progress' | 'On Hold' | 'Resolved' | 'Closed';

export type CaseRow = {
  id: number;
  case_id: string;
  title: string;
  severity: string;
  priority: string;
  status: CaseStatusValue;
  verdict: string;
  assignee: string | null;
  tags: string[];
  alert_count: number;
  created_at: string;
};

export type CaseEvent = {
  id: number;
  kind: string;
  message: string;
  actor: string | null;
  created_at: string;
};

export type CaseDetail = CaseRow & {
  description: string;
  summary: string;
  correlation_uid: string;
  severity_ai: string;
  confidence_ai: string;
  priority_ai: string;
  verdict_ai: string;
  investigation_report_ai_json: string;
  alerts: Alert[];
  events: CaseEvent[];
};

export type AuditRow = {
  id: number;
  action: string;
  actor: string | null;
  object: string | null;
  changes: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
};

const qs = (params: Record<string, string>) => {
  const q = new URLSearchParams(params).toString();
  return q ? `?${q}` : '';
};

export const alertsApi = {
  list: (params: Record<string, string> = {}) =>
    api<Page<Alert>>(`/api/alerts/${qs(params)}`),
  patch: (id: number, body: Record<string, unknown>) =>
    api<Alert>(`/api/alerts/${id}/`, { method: 'PATCH', body }),
};

export const casesApi = {
  list: (params: Record<string, string> = {}) =>
    api<Page<CaseRow>>(`/api/cases/${qs(params)}`),
  create: (body: { title: string; severity?: string; priority?: string; tags?: string[] }) =>
    api<CaseDetail>('/api/cases/', { method: 'POST', body }),
  detail: (id: number) => api<CaseDetail>(`/api/cases/${id}/`),
  patch: (id: number, body: Record<string, unknown>) =>
    api<CaseDetail>(`/api/cases/${id}/`, { method: 'PATCH', body }),
  linkAlerts: (id: number, alertIds: number[]) =>
    api<{ linked: number; total: number }>(`/api/cases/${id}/alerts/`, {
      method: 'POST',
      body: { alert_ids: alertIds },
    }),
  investigate: (id: number) =>
    api<{ case: CaseDetail; degraded: string[]; ms: number; mode: string }>(
      `/api/cases/${id}/investigate/`,
      { method: 'POST' },
    ),
  ask: (id: number, question: string, history: { role: string; content: string }[]) =>
    api<{ answer: string; mode: string; ms: number }>(`/api/cases/${id}/ask/`, {
      method: 'POST',
      body: { question, history },
    }),
  enrich: (id: number) =>
    api<{ case: string; iocs: { value: string; type: string }[]; results: EnrichmentRow[] }>(
      `/api/cases/${id}/enrich/`,
      { method: 'POST' },
    ),
};

export const auditApi = {
  list: (params: Record<string, string> = {}) =>
    api<Page<AuditRow>>(`/api/audit/${qs(params)}`),
};

export type KnowledgeItem = {
  id: number;
  title: string;
  body: string;
  tags: string[];
  source: string;
  case_id: number | null;
  case: string | null;
  created_at: string;
};

export type KbHit = { id: number; title: string; body: string; tags: string[]; score: number };

export const knowledgeApi = {
  list: () => api<{ count: number; results: KnowledgeItem[] }>('/api/knowledge/'),
  search: (q: string) =>
    api<{ count: number; results: KbHit[]; query: string }>(`/api/knowledge/?q=${encodeURIComponent(q)}`),
  create: (body: { title: string; body: string; tags: string[] }) =>
    api<KnowledgeItem>('/api/knowledge/', { method: 'POST', body }),
  remove: (id: number) => api(`/api/knowledge/${id}/`, { method: 'DELETE' }),
  extract: (caseId: number) =>
    api<{ case: string; created?: number; skipped?: string; titles?: string[] }>(
      '/api/knowledge/extract/',
      { method: 'POST', body: { case_id: caseId } },
    ),
};

export type EnrichmentRow = {
  ioc_value: string;
  ioc_type: string;
  provider: string;
  verdict: string;
  data: Record<string, unknown>;
  updated_at?: string;
};

export type EnrichmentProvider = {
  id: number;
  name: string;
  kind: string;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
};

export const enrichmentApi = {
  results: (q = '') => api<{ count: number; results: EnrichmentRow[] }>(`/api/enrichment/${qs({ q })}`),
  providers: () => api<{ results: EnrichmentProvider[] }>('/api/enrichment/providers/'),
  createProvider: (body: { name: string; kind: string; config: Record<string, unknown> }) =>
    api<EnrichmentProvider>('/api/enrichment/providers/', { method: 'POST', body }),
  patchProvider: (id: number, body: Record<string, unknown>) =>
    api<EnrichmentProvider>(`/api/enrichment/providers/${id}/`, { method: 'PATCH', body }),
  removeProvider: (id: number) => api(`/api/enrichment/providers/${id}/`, { method: 'DELETE' }),
};

export type RunStep = { index: number; type: string; status: string; detail: string; ms: number };

export type Playbook = {
  id: number;
  name: string;
  description: string;
  definition: string;
  enabled: boolean;
  builtin: boolean;
  steps_preview: string[];
  updated_at: string;
};

export type PlaybookRun = {
  id: number;
  playbook_id: number;
  playbook: string;
  case_id: number | null;
  case: string | null;
  status: string;
  mode: string;
  steps: RunStep[];
  error: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  created_by: string | null;
};

export const playbooksApi = {
  list: () => api<{ results: Playbook[] }>('/api/playbooks/'),
  run: (id: number, caseId?: number | null) =>
    api<PlaybookRun>(`/api/playbooks/${id}/run/`, {
      method: 'POST',
      body: caseId ? { case_id: caseId } : {},
    }),
  runs: (params: Record<string, string> = {}) =>
    api<{ count: number; results: PlaybookRun[] }>(`/api/playbooks/runs/${qs(params)}`),
  runDetail: (id: number) => api<PlaybookRun>(`/api/playbooks/runs/${id}/`),
  save: (id: number, definition: string) =>
    api<Playbook>(`/api/playbooks/${id}/`, { method: 'PATCH', body: { definition } }),
  remove: (id: number) => api(`/api/playbooks/${id}/`, { method: 'DELETE' }),
};

export type DashboardStats = {
  alerts: {
    total: number;
    last_24h: number;
    unassigned: number;
    by_severity: Record<string, number>;
    by_status: Record<string, number>;
  };
  cases: {
    total: number;
    open: number;
    by_status: Record<string, number>;
  };
  recent_alerts: {
    id: number;
    alert_id: string;
    title: string;
    severity: string;
    status: string;
    correlation_uid: string;
    created_at: string;
  }[];
  recent_cases: {
    id: number;
    case_id: string;
    title: string;
    severity: string;
    status: string;
    alert_count: number;
    created_at: string;
  }[];
};

export const dashboardApi = {
  stats: () => api<DashboardStats>('/api/dashboard/'),
};
