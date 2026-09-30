# MIGRATION.md — Original LLM call sites → IntrovertSOC `local_engine`

Source audited: `FunnyWolf/agentic-soc-platform` @ `master` (zip downloaded and grepped for
`LLMAPI`, `ChatOpenAI`, `with_structured_output`, `langchain_openai`, `langchain_core`,
`.invoke(`, and hardcoded `https://` endpoints). This file tracks every original LLM/external-AI
touchpoint and its status in IntrovertSOC.

Legend: **REMOVED** = feature/config deleted · **REWIRED** = intent kept, now routed exclusively
through `backend/llm/local_engine.py` · **REPLACED** = superseded by a new IntrovertSOC module.

## A. Backend LLM call sites (all of them)

| # | Original location | What it did | Status | IntrovertSOC destination |
|---|---|---|---|---|
| 1 | `backend/integrations/llm/llmapi.py:22-53` — `LLMAPI.get_model()` → `langchain_openai.ChatOpenAI(model, base_url, api_key, proxy, http_client)` | The single gateway: provider list from DB (`LLMProviderConfig`: `base_url`, `api_key`, `proxy`, `tags`, `priority`), tag-based selection, temperature | **REWIRED + REMOVED** | `backend/llm/local_engine.py` — plain `httpx` → `http://127.0.0.1:<port>/v1/chat/completions`; internal dummy key `local` injected only if demanded; **no proxy, no provider list, no tags, no api_key storage** |
| 2 | `backend/apps/agentic/analysis/prompts.py:54-60` — `invoke_structured_llm()` = `LLMAPI().get_model(tag="structured_output").with_structured_output(schema).invoke([System,Human])` | Funnel for every structured AI output; prompts read from `data/playbooks/*/*_{en,zh}.md` | **REWIRED** | `local_engine.complete_json(messages, schema=PydanticModel)` — prompt-enforced JSON (local models are unreliable at native tool-calling), pydantic validation, one repair retry, then deterministic fallback |
| 3 | `backend/apps/agentic/analysis/analysis.py:28` — `generate_investigation_report()` → #2 (`INVESTIGATION_SYSTEM_PROMPT`) | Produces `InvestigationReport` for a case (triggered by button/playbook/worker) | **REWIRED (split into short nodes)** | `apps/agents/graphs.py::investigate_case` — LangGraph chain: load_context → summarize → assess(JSON) → report → persist; each node = one short `local_engine` call |
| 4 | `backend/apps/agentic/analysis/knowledge.py:74` → #2 (`INVESTIGATION_KNOWLEDGE_KEYWORD_PROMPT`) | LLM proposes search keywords for knowledge retrieval | **REWIRED** | `apps/knowledge/retrieval.py` — keyword proposal step via `local_engine.complete_json`, with regex-keyword fallback |
| 5 | `backend/apps/agentic/analysis/knowledge.py:126` → #2 (`KNOWLEDGE_EXTRACTION_PROMPT`) | Extracts reusable knowledge records from closed-case data | **REWIRED** | `apps/knowledge/extraction.py` — same pattern, called on case close; skips gracefully when model is down |
| 6 | `backend/custom/playbooks/case_summary.py:25` — `LLMAPI(temperature=0.0).get_model().invoke([SystemMessage, HumanMessage])` | Example custom playbook calling the LLM directly (bypassing the funnel) | **REPLACED** | Built-in YAML playbook `case_summary` whose `llm` step runs through `local_engine.complete()` (playbook runner forbids any other LLM path) |
| 7 | `backend/playbooks/investigation.py` — calls `run_case_analysis(...)` | Playbook wrapper around #3 | **REWIRED** | Playbook step `investigate` in `apps/playbooks/runner.py`, delegating to the same LangGraph flow as #3 |
| 8 | `backend/playbooks/knowledge_extraction.py` — calls knowledge extraction (#5) | Playbook wrapper around #5 | **REWIRED** | Playbook step `extract_knowledge` → `apps/knowledge/extraction.py` |
| 9 | `backend/apps/agentic/management/commands/run_agentic_*_worker.py` (case-analysis / module / playbook workers) | Background worker processes consuming Redis streams to run #3/#6/#7/#8 asynchronously | **REPLACED** | Single lightweight in-process background thread + synchronous endpoints; no Redis. Long runs (playbooks) execute in a thread, UI polls status |

There is **no other** `ChatOpenAI` / `.invoke(` / structured-output call site in the original
backend — items 1–9 are the complete inventory.

## B. Frontend surfaces that exposed cloud AI / API keys (REMOVED)

| # | Original location | What it exposed | Status |
|---|---|---|---|
| 10 | `frontend/src/pages/LLMProviderSettings.tsx` (fields `base_url`, `api_key`, provider name, test button) | Full cloud-provider editor incl. **API Key input** | **REMOVED** → replaced by **Model Settings** page: endpoint host/port, model label, GGUF path, health status, generated llamafile launch command — **no key field** |
| 11 | `frontend/src/config/resources.tsx:1031-1051` (`llm-providers` resource: `endpoint: '/settings/llm-providers/'`, `base_url` field) | Generic CRUD wiring for provider configs | **REMOVED** → `api/model/config` endpoints (admin-only) |
| 12 | `frontend/src/pages/AuditLogsSettings.tsx:51` (`'LLM Provider'` audit target) | Audit-log link target for provider changes | **REMOVED** → audit targets now include `model_config` |
| 13 | `frontend/src/components/PersonalCenterModal.tsx` (app **API Key** create/list/revoke for `agent_api`) | Local bearer tokens for the CLI/harness agent API | **REMOVED** (`agent_api` out of scope for IntrovertSOC) |

## C. External cloud services referenced by original defaults (REMOVED)

| # | Original location | Remote default | Status |
|---|---|---|---|
| 14 | `backend/apps/settings/models.py:32` — `ThreatIntelAlienVaultOTXConfig.base_url` default `https://otx.alienvault.com/api/v1` + `api_key` | AlienVault OTX cloud threat intel | **REMOVED** — no cloud TI baked in. `apps/enrichment` defaults to **local feed files** (`data/threat_feeds/*.csv`); user-owned MISP/OpenCTI URLs are opt-in providers only |
| 15 | `backend/apps/settings/models.py:49-59` — `ThreatIntelOpenCTIConfig` (+ `pycti` dependency) | OpenCTI server | **REMOVED** as shipped dependency/config; opt-in user URL only |
| 16 | `frontend/src/pages/ThreatIntelligenceSettings.tsx:37` — OTX form default + api_key | Cloud TI settings UI | **REMOVED** → Enrichment Providers UI lists local feeds + user-added endpoints |
| 17 | `backend/integrations/llm/llmapi.py:_http_client_kwargs` — HTTP(S) **proxy** support for LLM traffic | Configurable egress proxy | **REMOVED** (no cloud LLM ⇒ no proxy needed; loopback/local sources only) |
| 18 | `backend/pyproject.toml` — `langchain-openai`, `pycti`, `ldap3`, `django-storages[boto3]`, PyPI mirror `mirrors.aliyun.com` | Cloud SDKs / remote services / build mirror | **REMOVED** (see `NETWORK.md` §2.2) |

## D. Interface modes (new capability, no original counterpart)

`backend/llm/chat_modes.py` (**Work / Introvert / Super Introvert / Paranoid / Zen**) injects a
per-user system prompt on **every** `local_engine` call — the original had no communication-mode
concept. The verbosity mode deliberately does **not** apply to pure extraction/classification
nodes where output shape must stay stable. Each mode carries an answer token budget
(`chat_modes.MODE_MAX_TOKENS` / `budget()`), used by the ask + report nodes.

## Status log

- [x] Phase 1 — audit of original completed (this document) · `NETWORK.md` written
- [x] Phase 2 — `local_engine.py`, `chat_modes.py`, `health.py`, Model Settings page, live llamafile
  verification (Qwen3-4B served by llamafile 0.10.6 on 127.0.0.1:8080; 29/29 backend tests; frontend
  `tsc -b && vite build` clean; full csrf→login→status flow verified through the Vite dev proxy)
- [x] Phase 3 — alerts/cases/audit foundation (`apps.alerts` batch ingestion + correlation_uid
  filters, `apps.cases` CRUD + alert linking + timeline events, `apps.audit` recording logins/
  config/record edits, admin-only read API) + Alerts/Cases/Audit pages wired; 50/50 backend tests;
  live smoke: ingest → create case → link → detail → audit through the Vite proxy
- [x] Phase 4 — Dashboard/interface pass: `apps.dashboard` stats endpoint (alert totals/24h/
  unassigned + severity mix, open cases, recent lists) + Dashboard page with stat cards, live
  model-status widget (dot/latency/re-check), severity pills, clickable recent alerts/cases;
  52/52 backend tests; frontend build clean; stats verified live through the Vite proxy
- [x] Phase 5 — agent investigation nodes rewired: #3 = `apps.agents.graphs.investigate_case`
  (LangGraph load_context → summarize → assess JSON → report → persist, each node one short
  `local_engine` call, degraded-mode fallbacks, `POST /api/cases/<id>/investigate/` with model-down
  503 banner); #7 delegated via `run_investigation()` service — playbooks runner lands in Phase 7.
  62/62 backend tests; live Qwen3-4B run: 46 s, 0 degraded, mode fingerprint visible in report
- [x] Phase 6 — chat modes live on all user-facing calls: `POST /api/cases/<id>/ask/`
  (ask_agent = one mode-aware `local_engine` call, history capped at last 8 turns, health
  pre-check 503 banner) + "Ask the agent" chat panel on Case detail showing the active mode;
  investigation report node (Phase 5) already mode-aware; shared `format_case_context` between
  graph and ask. 68/68 backend tests; frontend build clean; live A/B on case 1: same question
  → super_introvert = 2-line clipped answer (3.1 s), work = full structured markdown (21 s)
- [x] Phase 7 — knowledge/enrichment/playbooks rewired:
  #4 `knowledge/retrieval.py` (LLM keyword proposal → regex fallback, multi-word phrase
  expansion, token scoring) wired into ask + load_context top-3; #5 `knowledge/extraction.py`
  (auto on case close + `POST /api/knowledge/extract/`, skips when model down); #8 playbook
  step `extract_knowledge`; #6 built-in `case_summary` YAML (llm step, whitelist runner);
  #7 investigate step delegates to `run_investigation()`; #9 background thread + run polling
  (no Redis); #14-16 `apps/enrichment` local CSV feed + opt-in user http_lookup providers,
  deterministic regex IOC extraction on Alert save, case enrich endpoint + pre-investigation
  enrichment. Frontend: Playbooks/Knowledge/Enrichment pages + nav. 113/113 backend tests;
  build clean; live: extraction created 2 items, KB search scored hits via real keyword
  proposal, `10.0.0.5 → malicious` via local feed, playbook runs 1-3 (triage_and_learn:
  enrich → investigate → extract all ok, thread + polling)
- [x] Phase 9 — final grep: no `LLMAPI`/`ChatOpenAI`/`api_key`/cloud-URL residue
  (source grep clean; hits only in these docs describing the original); `NETWORK.md` §4
  checklist executed — all 5 items checked with evidence (package audit, backend URL grep,
  `dist/` origin scan, live dead-port banner test with config reverted, outbound-target
  logging). Also authored the remaining ARCHITECTURE §2 companions: `README.md`, `LICENSE`
  (MIT + attribution), `docker-compose.yml` + Dockerfiles + nginx.conf (YAML-validated,
  not executed — no docker here), `scripts/start_llamafile.ps1`/`.sh`, root `.gitignore`.
- [x] Phase 10 — model-family adapter + adaptive context + 5 chat modes:
  `llm/adapter.py` (family detection → per-family `chat_template_kwargs` request shaping,
  ```thinking```-tag stripping, `context_info()` = DB override → server-reported → 32768
  default, `wants_inline_kb()` at ≥128k); `llm/health.py` parses `context_length` from
  `/v1/models`; `chat_modes` +Paranoid (assume-breach, 4096 tokens) +Zen (768) with
  `MODE_MAX_TOKENS`/`budget()` wired into ask + report; `knowledge/retrieval.context_block()`
  = full-KB inline dump on big-context models, top-3 keyword search otherwise (ask +
  load_context); `ModelConfig.context_window` override (migration 0002, admin UI field,
  status shows `family`/`context_window`/`context_source`); frontend: Paranoid/Zen in the
  mode switcher, `body[data-chat-mode]` density CSS (zen 0.92×, super 0.96×), Model
  Settings family/context display. 126/126 backend tests; `tsc -b && vite build` clean;
  live: status `family=qwen3 ctx=default`, override 131072 → `context_source=override`,
  mode switch paranoid → live ask (28 s, mode=paranoid) → reset.
