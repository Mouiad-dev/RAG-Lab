# RAG Lab v2 — Build Progress

> **Read this first in any new session.** It tracks the plan and exactly what has been built.
> Source of truth for the design: `PLAN_1.md` (roadmap) and `PRODUCT.md` (numeric targets).

## How we work (the contract)

- Build **layer by layer, one small sub-step at a time**.
- **Explain-and-pause:** each sub-step is explained (concept + design pattern) and approved
  **before** any code is written.
- **Everything in Docker**, including Ollama (LLM + embeddings). Nothing required on the host.
- **No fakes in the product** — real tools only. Test doubles live only inside unit tests.
- Django-native (ORM, not raw SQL — except the one quarantined pgvector `<=>` fragment).
- After each sub-step: update this file **and** `ai-learning.md`.

## Milestone cuts

- **v0.1 (demo-able):** Phases 0–5 — one real chunker + naive/hybrid + real embedder + real
  LLM + generation + evals, end-to-end.
- **v0.5 (the lab):** + all 8 chunkers, Axis-2 upgrades, Pipeline Inspector, observability.
- **v1.0 (complete):** + all Axis-3 architectures, async queue at scale, advisor, fan-out,
  memory, tool calling, CI merge gate, deploy, MCP.

## Phase / step checklist

### Phase 0 — Foundations & the finish line
- [x] **0.1** Clean slate + write `PRODUCT.md` (numeric targets) + set up `PROGRESS.md` & `ai-learning.md`
- [x] **0.2** Minimal Django project (`config/` + `manage.py`), pinned deps — `manage.py check` passes
- [ ] **0.3** `docker-compose.yml`: postgres+pgvector, ollama, web (pinned versions) — `docker compose up` boots
- [ ] **0.4** `/health/` endpoint confirming DB + Ollama reachable

### Phase 1 — Data model (ORM) + LLM/Embeddings Ports
- [ ] Models: `Document`, `Chunk`(vector), `GoldenQuestion`, `Job`, `LLMCall`
- [ ] LLM Port + Adapter (Ollama dev / Anthropic demo / Fake for tests)
- [ ] Embeddings Port + Adapter

### Phase 2 — Ingestion + AXIS 1 (8 chunkers) + async queue
- [ ] Ingestion pipeline (route → extract → chunk → embed → store)
- [ ] Celery + Redis async ingestion; `Job` status live in UI
- [ ] 8 chunkers behind one `Chunker` interface (Fixed-Size first)
- [ ] Auto-advisor (heuristics)

### Phase 3 — Retrieval + AXIS 2 upgrades
- [ ] `naive` then `hybrid` (dense + BM25 + RRF) behind `Retriever` interface + Factory
- [ ] Metadata pre-filter, query transform, rerank, context engineering

### Phase 3b — Per-file strategy + multi-file parallel query (fan-out/fan-in)
### Phase 4 — Generation (grounded answer + Pydantic citations + honest IDK)
### Phase 5 — Eval harness (recall@k, faithfulness, latency, cost)
### Phase 6 — Prompt & context engineering + caching
### Phase 6b — Observability + Pipeline Inspector (Phoenix + Prometheus/Grafana)
### Phase 7 — Tool calling
### Phase 8 — AXIS 3 architectures (CRAG, GraphRAG, Multimodal, Agentic, Text-to-SQL)
### Phase 8b — Memory layer (Mem0)
### Phase 9 — Production hardening + CI/CD merge gate
### Phase 10 — MCP server (OAuth 2.1)

## Change log

- **0.1** — Deleted old scaffolding (`Dockerfile`, `docker-compose.yml`, `requirements.txt`,
  `Readme.md`, `.env.example`, old `PRODUCT.md`). Wrote fresh `PRODUCT.md` with the 5 targets +
  red lines. Created `PROGRESS.md` and `ai-learning.md`. No app code yet.
- **0.2** — `requirements.txt` pinned (Django 5.2.17 LTS, psycopg[binary] 3.3.5). Ran
  `startproject config .` → `config/{settings,urls,wsgi,asgi}.py` + `manage.py`. Annotated
  settings with TODO markers (env secrets → Phase 9; Postgres/pgvector → 0.3/Phase 1). DB is
  SQLite for now so the skeleton boots with no external services. `manage.py check` → 0 issues.
