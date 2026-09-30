# IntrovertSOC — Architecture

IntrovertSOC is an offline-capable, privacy-first reimagining of
[FunnyWolf/agentic-soc-platform](https://github.com/FunnyWolf/agentic-soc-platform) (MIT).
It keeps the intent of the original — agents that triage alerts, investigate cases, enrich
IOCs, and write reports — but replaces every cloud LLM API-key integration with a single
local llamafile server, ships a redesigned interface, and never phones home.

Companion documents:

- `NETWORK.md` — the complete outbound-connection allowlist and what was removed vs. the original.
- `MIGRATION.md` — every LLM call site of the original project and how it maps to `local_engine`.
- `docs/RECOMMENDED_MODELS.md` — which GGUF models to run.

---

## 1. Design principles

1. **One LLM door.** Exactly one module (`backend/llm/local_engine.py`) may open network
   connections to an LLM. No other file imports an LLM client, no cloud SDK exists in the
   dependency tree, and no API-key field exists anywhere in config or UI.
2. **Reliability over cleverness.** Agent flows are chains of short, single-purpose LLM calls
   that a mid-size local model (4B–27B) can execute correctly, with deterministic Python
   fallbacks when the model returns garbage. No giant multi-tool agentic loops.
3. **Offline-first data.** SQLite for all state (plus an embedded `sqlite-vec` extension for
   vectors). No Postgres, no Redis, no message broker, no object storage.
4. **Pluggable edges.** Alert sources, enrichment providers, and playbook steps are small
   Python modules discovered through registries — same spirit as the original, less machinery.
5. **Nothing leaves the machine** except (a) calls to user-configured SIEM/webhook sources and
   (b) `http://127.0.0.1:<port>` for the local llamafile server. See `NETWORK.md`.

---

## 2. Repository layout

```
IntrovertSOC/
├── ARCHITECTURE.md            # this file
├── NETWORK.md                 # outbound connection policy + removals vs original
├── MIGRATION.md               # original LLM call sites → local_engine mapping
├── README.md                  # what it is, llamafile setup, chat modes, differences
├── LICENSE                    # MIT (credits original project)
├── docs/
│   └── RECOMMENDED_MODELS.md  # top 10 GGUF models for SOC agent work
├── docker-compose.yml         # backend + frontend (llamafile runs separately)
│
├── backend/                   # Django project (managed with uv, Python 3.13)
│   ├── pyproject.toml
│   ├── .env.example           # LLAMAFILE_* variables — no API keys, ever
│   ├── manage.py
│   ├── introvertsoc/          # Django project package
│   │   ├── settings.py        # SQLite, session auth, CORS off (same-origin), env loading
│   │   ├── urls.py            # /api/..., /api/auth/..., /api/webhook/<token>/, /admin/
│   │   └── wsgi.py / asgi.py
│   ├── llm/                   # ← THE single point of LLM integration
│   │   ├── local_engine.py    # httpx client to llamafile OpenAI-compatible endpoint
│   │   ├── adapter.py         # model family detect + request shaping + context window
│   │   ├── chat_modes.py      # Work / Introvert / Super / Paranoid / Zen prompts + budgets
│   │   ├── health.py          # server ping + cached status (+ context_length parse)
│   │   └── schemas.py         # pydantic output schemas + JSON repair helper
│   ├── apps/
│   │   ├── accounts/          # local users, roles, login/logout, per-user prefs (chat_mode)
│   │   ├── alerts/            # Alert model, ingestion API, correlation keys
│   │   ├── sources/           # pluggable alert-source adapters (webhook/splunk/elk/…)
│   │   ├── cases/             # Case, IOC, timeline events, investigation reports
│   │   ├── agents/            # LangGraph graphs + short node functions (call llm/)
│   │   ├── enrichment/        # pluggable enrichment adapters (local feeds by default)
│   │   ├── knowledge/         # closed-case learnings, vector + FTS retrieval
│   │   ├── playbooks/         # YAML playbook definitions + sequential runner
│   │   ├── audit/             # append-only audit log (auth + CRUD + agent runs)
│   │   ├── dashboard/         # stats endpoints for charts
│   │   └── settings/          # runtime model config (host/port/model path), health API
│   ├── data/
│   │   ├── prompts/           # agent prompt templates (markdown), mode-aware
│   │   ├── threat_feeds/      # sample local reputation lists (CSV/JSON)
│   │   └── playbooks/         # built-in YAML playbooks
│   └── scripts/
│       └── fake_llm_server.py # OpenAI-compatible test double (offline tests)
│
├── frontend/                  # Vite + React 19 + TypeScript + Tailwind v4
│   ├── src/
│   │   ├── pages/             # Login, Dashboard, Alerts, Cases, CaseDetail,
│   │   │                      # Playbooks, KnowledgeBase, ModelSettings, AuditLog
│   │   ├── components/        # sidebar, topbar (mode switcher), tables, IOC chips,
│   │   │                      # timeline, ask-agent panel, SVG charts, status widget
│   │   ├── api/               # typed fetch client (session cookie + CSRF)
│   │   ├── stores/            # auth, chat-mode, theme
│   │   └── theme/             # tokens: dark-first + light, deep-teal accent
│   └── vite.config.ts         # dev proxy → backend; prod nginx same-origin
│
├── models/                    # (gitignored) user-supplied GGUF files
└── scripts/
    └── start_llamafile.ps1 / .sh   # convenience wrapper (binary NOT bundled)
```

---

## 3. Backend / frontend split

```
 Browser (SPA)
   │  session cookie + CSRF, same-origin /api
   ▼
 Django + DRF  ──────────────── SQLite (+ sqlite-vec, FTS5)
   ├── REST API  /api/alerts /api/cases /api/playbooks /api/knowledge ...
   ├── Auth      /api/auth/login|logout|me   (local users, roles: admin/analyst/viewer)
   ├── Webhook   /api/webhook/<source_token>/   (ingestion, token-authenticated)
   ├── Settings  /api/model/status , /api/model/config  (LLM endpoint config + health)
   └── llm/local_engine.py  ──HTTP──▶ http://127.0.0.1:<LLAMAFILE_PORT>/v1/...
                                        (llamafile, user-started process)

 Alert sources (Splunk/ELK/webhook pollers) ──HTTP──▶ user's own SIEM, only if configured
```

- **Backend owns:** data model, correlation, enrichment, agent orchestration (LangGraph),
  audit, auth, LLM access. Never exposes an LLM API key (none exists).
- **Frontend owns:** presentation, the chat-mode switcher (persisted per user via API),
  theme toggle (localStorage), polling of `/api/model/status`.
- **Dev:** `uvicorn`/`runserver` on `127.0.0.1:8000`, Vite dev server proxies `/api`.
- **Prod (compose):** nginx serves the built SPA and proxies `/api` to the backend container;
  llamafile runs on the **host**, reachable as `http://host.docker.internal:8080`.

### Why SQLite, no Redis, no websockets (vs. original)

The original depends on Postgres, Redis streams, channels/websockets, background worker
commands, and LDAP. For a single-analyst offline tool this is fragile setup weight. The spec
explicitly favors simplification and reliability, so: SQLite, synchronous request-time agent
runs for short jobs, a single background **thread** for long-running pollers/playbooks with
status polled by the UI, and HTTP polling instead of realtime push. Functionality intent is
preserved; the transport is simpler.

---

## 4. The LLM connector (single point of integration)

### 4.1 `backend/llm/local_engine.py`

The **only** module allowed to talk to an LLM.

```
Config (.env, overridable at runtime via Settings page → DB)
  LLAMAFILE_BASE_URL   default http://127.0.0.1:8080   (host+port configurable)
  LLAMAFILE_MODEL      default local-model              (sent as "model", cosmetic)
  LLAMAFILE_PORT       default 8080                     (derived base URL if BASE_URL unset)
  LLAMAFILE_TIMEOUT    default 120 (read), 5 (connect)  (local inference can be slow)
  LLAMAFILE_API_KEY    default "local"                  (INTERNAL ONLY, never shown/stored in UI)

API (imported by agents/, playbooks/, knowledge/, chat endpoints — nothing else):
  complete(messages, *, mode=None, temperature=0.0, timeout=None) -> str
  complete_json(messages, *, schema: pydantic model, mode=None) -> BaseModel
  health_check(force=False) -> HealthStatus   (cached ≤ 15s)
  model_info() -> {"base_url", "model", "connected", "server_model_id", ...}
```

Behavior:

- **Transport:** plain `httpx` against `{base}/v1/chat/completions` (llamafile's
  OpenAI-compatible endpoint). No `langchain`, no `langchain-openai`, no cloud SDK at all —
  therefore **no API-key surface**. If the endpoint ever demands a key, the internal dummy
  value `local` is injected in the request header only.
- **Chat-mode injection:** every call prepends the system prompt for the currently selected
  mode (from `chat_modes.py`), unless the caller passes `mode=None` explicitly for raw calls
  used by pure-JSON pipeline nodes (those set `mode="work"` explicitly).
- **Retries:** 3 attempts, exponential backoff (0.5s/1.5s/3.5s), retrying connect errors,
  read timeouts, and 5xx. No retry on 4xx (except one JSON-repair round-trip, below).
- **Structured output (`complete_json`):** local models are unreliable at tool-calls, so we do
  **not** use function/tool calling. Instead: prompt-enforced JSON → strict `pydantic`
  validation → on failure, one *repair* retry that feeds the validation error back → on second
  failure, raise `LLMOutputError` which the caller converts into a deterministic fallback.
- **Health:** `GET {base}/v1/models` (fallback `GET {base}/`), 3s timeout, cached 15s.
  Surfaced by `GET /api/model/status` and shown in the Model Settings page, Dashboard widget,
  and a dismissible top banner when down: *"Local model server not detected — start your
  llamafile at `<base_url>` to enable AI features."* The app **never crashes or blocks**
  on a missing model: non-LLM features stay fully usable.

### 4.2 Swapping models without code changes

- GGUF/model identity lives in `.env` **or** in the DB-backed runtime config edited from the
  **Model Settings page** (host, port, model name, GGUF path) — no file editing required.
- Because llamafile loads a GGUF at process start, the page shows a generated, copy-pasteable
  launch command for the selected path, e.g.
  `llamafile-0.10.6.exe -m "C:\...\qwen3-4b-q4_k_m.gguf" --port 8080 --host 127.0.0.1`,
  plus a "Test connection" button that re-runs the health check against the edited endpoint.
- `LLAMAFILE_MODEL` only labels requests; the actual weights are whatever the llamafile
  process was started with, and the page also shows the model id the server reports.

### 4.3 Chat modes — `backend/llm/chat_modes.py`

```
MODE_REGISTRY = {
  "work":     WorkModePrompt,      # default: senior-analyst briefings, reasoning + next steps
  "introvert": IntrovertPrompt,    # verdict + key evidence + 1-2 actions, bullets
  "super_introvert": SuperPrompt,  # terminal-style: STATUS/SEVERITY/ACTION only;
                                   # expands ONLY when the user asks "why"/"explain"
  "paranoid": ParanoidPrompt,      # assume-breach: hypothesis enumeration, verification
                                   # before remediation, fullest coverage (4096 tokens)
  "zen":      ZenPrompt,           # one calm paragraph: verdict, reason, one action (768)
}
get_system_prompt(mode) -> str            # injected by local_engine on every call
resolve_mode(user, requested=None) -> str # per-user DB setting; default "work"
budget(mode) -> int                       # MODE_MAX_TOKENS: answer-length cap per mode
```

- Persisted per user in `accounts` (column on user profile) — survives sessions, no sync.
- Switcher is a 5-way control in the top nav (always visible, tooltips per mode) →
  `PUT /api/auth/me/preferences {"chat_mode": ...}`; `/api/auth/modes/` serves the list.
- UI density follows the mode: `body[data-chat-mode]` (zen 0.92×, super_introvert 0.96×).
- Every mode-gated call path (investigation report, ask-agent chat, playbook LLM steps)
  passes the caller's mode; pure classification/extraction nodes use fixed short prompts
  unaffected by verbosity mode (output shape must not change with mode).

### 4.4 Model-family adapter — `backend/llm/adapter.py`

- `detect_family()` / `resolve_family()` classify the served model (mimo / qwen3 / qwen /
  gpt-oss / mistral / gemma / phi / llama / unknown) from the server-reported id, GGUF path
  and label; `request_shaping(family)` adds `chat_template_kwargs.enable_thinking=false` for
  the Qwen3/MiMo template family (they ship the same ```thinking``` protocol) and
  `strip_thinking_tags()` removes any reasoning block that leaks into content.
- `context_info()` resolves the effective context window: DB override
  (`ModelConfig.context_window`, admin UI, 0 = auto) → server-reported `context_length`
  (parsed from `/v1/models` by `health.py`) → 32768 default.
- `wants_inline_kb()` (≥131072 tokens) switches knowledge retrieval: **inline the entire
  knowledge base** into the prompt (`retrieval.context_block()`), otherwise keep top-3
  keyword search. No new network egress — everything still goes through the cached
  loopback health check.

---

## 5. Data model (core)

```
accounts:   User (Django), Role=admin|analyst|viewer, chat_mode, theme
alerts:     Alert{id, source, external_id, title, severity, event_time, raw JSON,
                  iocs[], case?, correlation_key, created_at}
sources:    Source{name, kind, config JSON, token, enabled, last_polled_at}
cases:      Case{title, status, severity, confidence, verdict, summary,
                 created_at, closed_at, owner}
            IOC{id, case, type, value, first_seen, enrichment JSON}
            TimelineEvent{case, ts, kind, message, actor}      # human + agent + system
            Report{case, kind: investigation|playbook, content md, mode, model, created}
enrichment: Enrichment{ioc, provider, result JSON, created_at}
knowledge:  KnowledgeItem{title, body, tags[], case_ref, embedding? , created_at}
playbooks:  Playbook{name, description, definition YAML, enabled}
            PlaybookRun{playbook, case?, status, steps JSON, started, finished}
dashboard:  derived from Alert/Case aggregates (no cache table needed at this scale)
audit:      AuditLog{ts, actor, action, object_type, object_id, detail JSON} (append-only)
settings:   ModelConfig{base_url, model, gguf_path, context_window, updated_at}  # overrides .env
```

IOC extraction is **deterministic regex first** (IPs, domains, hashes, URLs, emails), then
augmented (never replaced) by model-suggested IOCs in the agent pipeline.

Correlation into Cases (deterministic, not LLM): alerts sharing an IOC value, host, user, or
`correlation_key` within a sliding window (default 24h) are attached to the same Case; manual
case creation always available.

---

## 6. Agent design (LangGraph, short nodes)

`backend/apps/agents/graphs.py` — one `StateGraph` per flow, **each node is one small
`local_engine` call with a single job** and deterministic pre/post-processing:

```
investigate_case (on-demand or on alert-batch):
  [load_context]  → pure Python: case JSON, IOCs, enrichments, KB retrieval (top 3)
  [summarize]     → 1 call: 5-8 line case summary
  [assess]        → 1 call: JSON {severity, confidence, verdict, rationale, next_steps[]}
  [report]        → 1 call: markdown investigation report (mode-aware verbosity)
  [persist]       → pure Python: save Report, timeline events, update Case fields
```

- Extract-IOCs inside the pipeline is code-first (regex), model only proposes additions.
- **Degraded-mode rule:** any node whose `complete_json` fails twice falls back to a
  deterministic default (e.g. keep prior severity, mark `confidence="low"`,
  report prefixed "partial — model output unusable"). Runs never hard-fail.
- `ask_agent` (Case panel) is a single call: case context + top-K knowledge + short chat
  history + selected mode. Not a graph — interactive Q&A must stay snappy.
- Playbook LLM steps call the same `local_engine` functions; playbook order itself is plain
  sequential Python (YAML steps), no planning loop.

---

## 7. Security & roles

- Local accounts only (Django password hashing, PBKDF2). No LDAP/SSO/OAuth by default.
- Roles: **admin** (users, settings, playbooks), **analyst** (cases, agents, playbooks runs),
  **viewer** (read-only). Enforced by DRF permissions + mirrored in UI.
- Webhook ingestion uses per-source random tokens in the URL (no login needed for machines).
- Session cookie (`HttpOnly`, `SameSite=Lax`) + CSRF; served same-origin, so no CORS wildcard.
- Audit log records logins, config changes, case/verdict edits, agent & playbook runs.

---

## 8. Frontend structure & visual identity

- **Stack:** Vite + React 19 + TypeScript + Tailwind CSS v4, react-router, typed fetch
  client. No AntD, no component library, no icon-font CDN — icons are inlined SVG.
- **Identity:** dark-first; neutral zinc/slate surfaces; single **deep-teal** accent;
  light mode via a top-bar toggle (persisted localStorage). Density is calm, not flashy —
  a tool for late-night triage.
- **Shell:** left sidebar (Dashboard / Alerts / Cases / Playbooks / Knowledge Base /
  Model Settings / Audit Log) + top bar (global search-free, mode switcher, model-status dot,
  theme toggle, user menu).
- **Key screens:**
  - *Dashboard*: alert volume over time (SVG area chart), open cases by severity (bars),
    model-status widget (green/amber/red + endpoint), recent activity.
  - *Case detail*: timeline layout, IOC chips (click → enrichment popover), report section,
    "Ask the agent" side panel with mode-aware responses.
  - *Model Settings*: endpoint/model/GGUF path editor, health status, generated llamafile
    launch command, history of last N health checks. **No API-key field.**
  - *Playbooks / Knowledge Base*: list + YAML editor / searchable cards with retrieval test.

---

## 9. Testing & verification strategy

| Layer | Approach |
|---|---|
| `local_engine` | unit tests + `scripts/fake_llm_server.py` (OpenAI-compatible) for retries, timeouts, JSON-repair; **live test** against real llamafile + downloaded GGUF |
| Ingestion/cases | `manage.py seed_demo` dummy data; API tests via Django test client |
| Agents | run pipeline against fake server (garbage JSON → fallback assertions) **and** live model |
| Chat modes | same input under 5 modes → live model output captured into docs; persistence test |
| Frontend | `tsc --noEmit` + `vite build`; visual check by rendering pages in a real browser |
| Docker Compose | authored + YAML-validated; **cannot be executed on this machine** (no docker) |

## 10. Dependency policy

Runtime backend: `django`, `djangorestframework`, `langgraph`, `httpx`, `pydantic`,
`python-dotenv`, `pyyaml`, `sqlite-vec` (optional, degrade to FTS5 if load fails).
Frontend: `react`, `react-dom`, `react-router`, `tailwindcss`, `vite`, `typescript`.
**Explicitly absent:** `langchain`, `langchain-openai`, `openai`, `anthropic`, telemetry,
analytics, update-checker, or any package that opens non-allowlisted connections at runtime
(see `NETWORK.md`).
