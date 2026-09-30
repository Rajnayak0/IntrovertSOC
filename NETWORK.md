# IntrovertSOC — Network Policy

This document is the **complete** list of network connections IntrovertSOC is allowed to make.
Anything not listed here is a bug. It also records what was removed relative to the original
FunnyWolf/agentic-soc-platform project.

Auditing method: connection-relevant code paths were reviewed from the original repository
source; exact file references for the REMOVED section are backfilled from a full source grep
(the same grep feeds `MIGRATION.md`). The allowlist below governs IntrovertSOC by
construction: dependencies are allowlisted, and `backend/llm/local_engine.py` is the only
module that may open an LLM connection.

---

## 1. Outbound connections ALLOWED at runtime

| # | Destination | Protocol / port | Purpose | Trigger | User control |
|---|---|---|---|---|---|
| 1 | **`http://127.0.0.1:<LLAMAFILE_PORT>`** (default `8080`) | HTTP, loopback only by default | llamafile OpenAI-compatible endpoint: `/v1/chat/completions`, `/v1/models` (health), `/v1/embeddings` (KB embeddings) | Every LLM call; health check (cached ≤15 s); explicit "Test connection" | Host/port/model in `.env` **or** Model Settings page. Default binds loopback; docs instruct never to expose the llamafile beyond localhost |
| 2 | **User-configured SIEM / log sources** — e.g. `https://splunk.internal:8089`, `https://es.corp.local:9200` | HTTPS/HTTP, whatever the user's source uses | Pull alerts by query (Splunk / Elasticsearch / OpenSearch adapters) | Source poller (`manage.py run_source_pollers`) — only sources the user created and enabled | Per-source config in the UI; disabled sources are never contacted |
| 3 | **User-configured enrichment endpoints** (optional, off by default) | HTTPS/HTTP | User's *own* threat-intel server (e.g. self-hosted MISP/OpenCTI) or internal reputation service | IOC enrichment, only for providers the user added | Per-provider config; **default install ships local-file feeds only** |
| 4 | **User-configured playbook HTTP actions** (optional) | HTTPS/HTTP | Destinations the user wrote into their own playbook YAML (`http_request` steps) | Playbook run, at the exact URL the user authored | Editable playbook definitions |
| 5 | *(Inbound, not outbound)* Webhook ingestion `POST /api/webhook/<token>/` | HTTP | SIEM/vendor pushes alerts to IntrovertSOC | When the user's system sends data | Per-source random token; endpoint disabled if source disabled |

**Loopback rule:** destination #1 defaults to and is documented as `127.0.0.1`. The only
reason host/port are configurable is Docker (`host.docker.internal`) and advanced users who
run llamafile on another machine **they own** — the app makes no connection to any
third-party host under default settings.

**Rows 2, 4 and 5 are policy placeholders for features not implemented:** IntrovertSOC
ships no source pollers, no `http_request` playbook step (the runner's whitelist is
`log | llm | investigate | extract_knowledge | enrich`), and no token webhook endpoint.
Alert ingestion is push-only via the authenticated `POST /api/alerts/` (single/batch).
If any of these features is ever added, its destinations must be exactly as described
here: user-authored URLs only, opt-in, disabled by default.

**Browser:** the SPA talks only to its own origin (`/api/...`, same-origin, no CORS
wildcards, no cross-origin requests). Fonts and icons are bundled — no font/CDN requests.

### Explicitly NOT allowed (enforced by dependency policy + code review)

- Any cloud LLM provider (OpenAI, Anthropic, Google, Mistral, Groq, DeepSeek, OpenRouter…)
- Any API key stored, transmitted, or displayed
- Telemetry, analytics, crash reporters (Sentry etc.), usage pings
- Update/version checkers, license checkers, phoning home to any project website
- Remote font/icon/CDN assets at runtime
- DNS or HTTP to any host not entered by the user in settings
- Default-install connections to any threat-intelligence SaaS (VirusTotal, AbuseIPDB, …)

---

## 2. REMOVED from the original project

### 2.1 Cloud LLM integration (the core removal)

| Original | What it did | IntrovertSOC |
|---|---|---|
| `backend/integrations/llm/llmapi.py` (`LLMAPI.get_model()` → `langchain_openai.ChatOpenAI`) | Instantiated an OpenAI-compatible client with user-supplied `base_url`, **`api_key`**, temperature, and optional HTTP **proxy** (`httpx.Client(proxy=...)`) — the gateway for every AI feature | Replaced by `backend/llm/local_engine.py`: plain `httpx` → `127.0.0.1`, internal dummy key `local` injected only if demanded, **no proxy option**, no provider list, no tags |
| `langchain-openai` dependency (`backend/pyproject.toml`) | Pulls the `openai` cloud SDK into the backend | **Removed entirely** (also removes `langchain-core`'s OpenAI path). No `openai`/`anthropic`/`langchain-openai` anywhere in the tree |
| LLM provider config in DB + `frontend/src/pages/LLMProviderSettings.tsx` | UI form to create multiple providers with **API key fields**, model names, base URLs, tags | **Removed.** Replaced by *Model Settings*: endpoint host/port, model label, GGUF path, health status. **Zero API-key fields in UI, DB, env, or docs** |
| `get_llm_configs()` runtime config + provider "tags" routing (`structured_output`, etc.) | Selected among several cloud providers/models per task | **Removed.** Single configured endpoint; model choice = which GGUF you started llamafile with |

### 2.2 Other cloud/remote services in the original dependency set

| Original dependency / feature | Remote target | IntrovertSOC |
|---|---|---|
| `django-storages[boto3]` | AWS S3 (object storage) | **Removed** — no cloud storage; files (if any) stay on local disk |
| `pycti` (OpenCTI client) | OpenCTI server (remote threat-intel platform) | **Removed** as a default dependency; enrichment defaults to local CSV/JSON feeds shipped in `data/threat_feeds/`. Users may still add their *own* MISP/OpenCTI URL as an opt-in provider |
| `ldap3` + `apps/accounts/ldap.py` | Corporate LDAP server | **Removed by default** — local users/roles only (spec: no third-party auth dependency). LDAP is not re-implemented |
| `channels-redis` / `django-redis` / Redis streams | — (infrastructure, not internet) | **Removed** (offline simplicity — no broker to install) |
| `psycopg2` (PostgreSQL) | — | **Removed** — SQLite |
| PyPI index pinned to `https://mirrors.aliyun.com/pypi/simple` in `backend/pyproject.toml` | Build-time package mirror | **Removed** — default PyPI at build time; **no** package index is contacted at runtime |
| Git submodules `asp-doc` (VitePress site on Cloudflare Pages) and `asp-marketplace` | External doc/plugin repos | **Not carried over** — no submodules, no doc-site tooling, no plugin marketplace in the fork |
| `frontend/public/fonts/JetBrainsMono/*` + `lucide-react`, `@ant-design/*` etc. | (fonts are bundled locally in original — no CDN found) | Original fonts are bundled, not CDN — nothing to remove there. IntrovertSOC uses a system font stack + inlined SVG icons instead, shrinking the dependency surface further |
| Links to `https://asp.viperrtp.com` in original README | Documentation website (click-through links only, not runtime calls) | **Not carried over** — our README links only to the original's GitHub repository for attribution |

### 2.3 Things checked and found NOT present in the original

To be accurate rather than alarmist: the original contains **no telemetry, no analytics, no
update-check, and no license-check code** (frontend `index.html` is clean; no
Sentry/segment/posthog-style dependencies in `frontend/package.json`). Nothing needed
removal there. IntrovertSOC's guarantee is stronger than "we didn't find any": the policy in
§1 means only allowlisted destinations can ever be contacted, and the dependency list is
closed.

**Out of scope features dropped** (capability removal, not network): LDAP auth, agent_api /
CLI harness integration, CMDB enrichment, ELK action worker, marketplace plugins, comments/
inbox/collaboration extras. Their absence removes their potential egress paths too.

---

## 3. Build-time network use (not runtime)

These happen while installing/building, never while the app runs:

- `uv pip install` → `pypi.org` (or an index the user configures)
- `npm install` / `vite build` → `registry.npmjs.org`
- `docker compose build` → `docker.io` base images (only if the user builds the images)
- Downloading a llamafile binary / GGUF model → whatever host the **user** downloads from
  (the repo does not bundle or auto-fetch either)

After build, all artifacts are local. For a fully air-gapped install: build on a connected
machine, copy the tree, run offline.

---

## 4. Enforcement checklist (executed at Phase 9)

- [x] `pip`-level audit (`uv pip list`): no `openai`, `anthropic`, `langchain-openai`,
      `boto3`, `sentry-*`, telemetry libraries. Allowlisted transitive deps: `langgraph`
      stack (`langchain-core`, `langgraph-*`, `langsmith` — hard-disabled in
      `settings.py`), `httpx`, `pyyaml`, `sqlite-vec` (installed, unused until vector
      search is enabled).
- [x] `grep` backend for `http://`/`https://` outside `local_engine.py`, source adapters,
      enrichment providers, playbook http steps → every hit is a loopback default
      (`llm/config.py`), a user-config validation string or example (`modelconfig`,
      enrichment `url_template`), a loopback CSRF origin, or a test fixture.
      **Zero hard-coded third-party hosts in source.**
- [x] Frontend build contains no external origins (scanned `dist/` for `https://`):
      found = `127.0.0.1`/`localhost` (same-origin API), `http://www.w3.org` (SVG
      namespace), `react.dev`/`reactrouter.com` (React Router error-message strings,
      never fetched), `misp.local` (example placeholder text in an input). No
      CDN/font/analytics origins.
- [x] Startup health check failure → UI banner, **zero** other outbound attempts.
      Live-tested: config override → `127.0.0.1:9`; `/api/model/status/` returned
      `connected=false` with the banner ("Local model server not detected — start your
      llamafile at …"), and the only connection attempted was the configured endpoint
      (immediately refused). Override reverted to the env default afterwards.
- [x] App logs every outbound target: `llm.local` logs `llm.complete ok target=…` at
      INFO (plus retry lines); `apps.enrichment` logs `enrichment http target=…` at INFO
      before each provider request (local-file feeds make no connection). Source-adapter
      loggers don't exist because source adapters aren't implemented (rows 2/5 below).
      Wireshark/packet capture left as an optional user step.
