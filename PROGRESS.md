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
- [x] **0.3** `docker-compose.yml`: postgres+pgvector, ollama, web (pinned versions) — `docker compose up` boots
- [x] **0.4** `/health/` endpoint confirming DB + Ollama reachable — **Phase 0 complete**

### Phase 1 — Data model (ORM) + LLM/Embeddings Ports
- [x] **1.1** Enable `pgvector` extension via `documents/0001` migration (`CreateExtension`) — verified `vector` v0.8.6 + `::vector` cast works. Created `documents` app; added `django.contrib.postgres`.
- [x] **1.2** `Document` model (fat model) + `DocumentRepository` — verified create/read/mark_ready/list against real DB; file on volume
- [x] **1.3** `Chunk` model (`VectorField` dim 1024) + `ChunkRepository.search_by_vector` (CosineDistance, ORM-native, collection pre-filter) — verified nearest-first ranking on real pgvector
- [x] **1.4** `Job` (documents), `GoldenQuestion` (new **evals** app), `LLMCall` **+ `CallCost`** (core) + repositories — verified against real DB. Cost SPLIT out of LLMCall into a 1:1 `CallCost` breakdown (input/output/cache_write/cache_read/total, currency, price_ref); usage stays on LLMCall (incl. cache_creation/cache_read tokens). Price = NO db model (Pydantic config in 1.5). PromptTemplate deferred (Phase 2/4); `prompt_ref` is a string.
- [x] **1.5a** LLM types + price book: `LLMResponse` (Pydantic), `LLMClient` (typing.Protocol), `ModelPrice`/`PRICE_BOOK`/`compute_cost` (Pydantic, no DB), `FakeLLM` (test-only). Verified cost math + FakeLLM satisfies Protocol.
- [x] **1.5b** Real `OllamaClient` (httpx → /api/chat) + `MeteredLLMClient` decorator (writes LLMCall+CallCost) + **registry-based** `build_llm_client()` (Protocol + Strategy + Factory + polymorphism, **no if/else**). Pulled `qwen2.5:0.5b`. Verified real call auto-wrote a $0 receipt; unknown provider errors cleanly.
- [x] **1.5c** `AnthropicClient` (real SDK, `@register_provider("anthropic")`, default `claude-opus-5`, checks stop_reason/timeout, optional workspace-id header). Verified real call (haiku) → 'Paris', real-dollar receipt $0.000042.
- [x] **1.6** Embeddings Port + Adapter (BGE-M3 via Ollama). Generic `common/ProviderRegistry` (DRY, reused by llm+embeddings+future axes). Verified **first real semantic search**: "money back?" → refund chunk (0.358) via real bge-m3 vectors + pgvector. **Phase 1 COMPLETE.**

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
- **0.3** — `Dockerfile` (python:3.13-slim) + `docker-compose.yml` with 3 pinned services:
  db=`pgvector/pgvector:pg16`, ollama=`ollama/ollama:0.34.0`, web (built). Named volumes
  (pgdata, ollama_data), healthchecks, web `depends_on: db healthy`. Switched Django DB to
  PostgreSQL driven by env vars; set `ALLOWED_HOSTS`; wrote `.env.example`; added
  `OLLAMA_BASE_URL` to `.env`. Cleanup: removed abandoned v1 orphan container + a pg17-init'd
  `pgdata` volume that was incompatible with pg16. Verified: `migrate` applied on pg16, and
  web reached `http://ollama:11434/api/version` → 0.34.0.
- **0.4** — Created `core` app (registered in INSTALLED_APPS). Added thin `health` view:
  checks DB (`SELECT 1`) + Ollama (`/api/version`), returns JSON with per-dependency status,
  **HTTP 200 if all ok else 503**. Wired `path("health/", ...)`. Verified BOTH paths: healthy
  → 200; forced Ollama failure → 503 with the error surfaced. **Phase 0 done.** (commit d055198)
- **1.1** — Created `documents` app; added `django.contrib.postgres` to INSTALLED_APPS. Wrote
  `documents/0001_enable_pgvector.py` using `CreateExtension("vector")` (ORM-native, reversible,
  reproducible on any fresh DB). Applied it. Verified in psql: `vector` v0.8.6 in `pg_extension`
  and `'[1,2,3]'::vector` casts. `documents/models.py` intentionally still empty (models = 1.2+).
- **1.2** — `Document` model (title, original_filename, `file` FileField, collection[notebook/
  golden], content_type, language, page_count, size_bytes, status, error, timestamps) with
  constraints + indexes in the model, and fat-model methods `mark_processing/ready/failed`.
  Added `DocumentRepository` (documents/repositories.py) — the only place `Document.objects` is
  touched (create/get/list_in_collection). File storage: Django `FileField` → `MEDIA_ROOT`
  volume, `STORAGES` set so S3/MinIO can swap in later (config, not code). Migration `0002_initial`.
  `media/` gitignored. Verified end-to-end against real Postgres, then cleaned up test row.

  **Storage decision:** original file bytes live on a mounted volume (not in the DB, not S3 yet).
  DB holds structured facts + vectors; fat bytes on disk. Swap to S3/MinIO is a Phase-9 config change.
- **1.3** — Added `pgvector==0.5.0` (rebuilt web image). `Chunk` model: FK→Document
  (CASCADE, related_name=chunks), text, ordinal, page (citation), token_count, metadata JSON,
  `vector = VectorField(dimensions=EMBEDDING_DIM=1024, null=True)`, unique(document, ordinal).
  ANN index (HNSW/IVFFlat) deferred with a NOTE (measure first). `ChunkRepository`:
  `bulk_create`, `list_for_document`, and 🔴 `search_by_vector` — the ONE quarantined vector
  search, done ORM-native via pgvector `CosineDistance` annotation + `.order_by("distance")`,
  with a **collection pre-filter** (Notebook/Golden isolation). Migration `0003_chunk`. Verified:
  hand-made 1024-dim vectors ranked A=0.0000 < C=0.0061 < B=1.0000 on real pgvector, then cleaned up.
- **1.4** — Three "lab memory" tables + repos, split by concern into a new `evals` app:
  `Job` (documents/models.py) — ingestion state machine (queued→extracting→chunking→embedding→
  ready/failed) with fat-model transition methods + started/finished timestamps; `JobRepository`.
  `GoldenQuestion` (evals/) — eval answer key (question, expected_answer, expected_source/page,
  language); `GoldenQuestionRepository`. `LLMCall` (core/) — immutable cost receipt (provider,
  model, purpose, prompt_ref string, tokens, cache_read_tokens, `cost_usd` Decimal, latency_ms);
  `LLMCallRepository.log()` writes LLMCall + CallCost atomically; `total_cost()` aggregates
  CallCost.total_cost. Migrations: core 0001 (LLMCall+CallCost), documents 0004, evals 0001.
  **Cost split (user call):** LLMCall = USAGE (tokens/latency), CallCost = MONEY (1:1 breakdown).
  Option A = every call always gets a CallCost ($0 for Ollama). Cache fully modeled: usage has
  cache_creation_tokens (write) + cache_read_tokens (read); cost has cache_write_cost +
  cache_read_cost. Cost field names carry no `_usd` (currency is its own field).
- **1.5a** — New `llm/` package (plain Python, not a Django app): `ports.py` (`LLMResponse`
  Pydantic + `LLMClient` `@runtime_checkable` Protocol — "no vendor type escapes the adapter"),
  `pricing.py` (`ModelPrice` + `PRICE_BOOK` for Opus5/Sonnet5/Haiku4.5 @ 2026-06-24 rates +
  `compute_cost` → `CostBreakdown`; Ollama free), `fakes.py` (`FakeLLM`, TEST-ONLY). Added
  `pydantic==2.12.3`. **Price = Pydantic ModelPrice (not a DB table)** — promote to DB only if
  runtime editing ever needed. Anthropic key stored in gitignored `.env` (user should rotate it).
  Verified: FakeLLM isinstance LLMClient; Haiku 1M in/out/cache-read = $1/$5/$0.10 = $6.10; $0 Ollama.
- **1.5b** — `llm/adapters/ollama.py` `OllamaClient` (httpx POST /api/chat, stream=False,
  temperature/num_predict options, maps prompt_eval_count/eval_count/done_reason → LLMResponse,
  reads OLLAMA_BASE_URL). `llm/metering.py` `MeteredLLMClient` (Decorator: wraps any LLMClient,
  computes cost via price book, writes LLMCall+CallCost in one place → "log on EVERY call").
  Added `httpx==0.28.1`; pulled `qwen2.5:0.5b` into the ollama_data volume. Verified a real call
  end-to-end wrote a $0 receipt with price_ref stamped, then cleaned up. **Note:** first call ~7.5s
  (model load) — not representative of warm p95.
  **Refactor (user call): no if/else in the factory.** Added `llm/registry.py` — a provider
  registry (`@register_provider("ollama")` on `OllamaClient`). `llm/adapters/__init__.py` imports
  each adapter so it self-registers; registry `_ensure_adapters_loaded()` self-loads on lookup.
  `build_llm_client()` now does a polymorphic registry lookup (`get_provider_builder`), no branching:
  Protocol (LLMClient) + Strategy (adapters) + Factory (registry) + polymorphism. Adding a provider
  = new adapter + one decorator + one import line; the factory never changes (open/closed).
- **1.5c** — `llm/adapters/anthropic.py` `AnthropicClient` (real `anthropic==1.6.0` SDK,
  `@register_provider("anthropic")`, default `claude-opus-5`, explicit timeout). Discipline:
  raises `TruncatedResponseError` on stop_reason=max_tokens and `RefusalError` on refusal (never
  ship garbage); does NOT forward `temperature` (modern Claude models reject sampling params → 400).
  Maps usage incl. cache_creation/cache_read tokens → LLMResponse. Optional `ANTHROPIC_WORKSPACE_ID`
  header for org-scoped keys. **Gotcha:** the first key was org-scoped (400 "not scoped to a
  workspace"); a workspace-scoped key fixed it. Verified real haiku call → 'Paris', receipt
  $0.000042 (22in×$1/M + 4out×$5/M) via the same MeteredLLMClient. **1.5 COMPLETE.**
  🔐 Both shared keys are in the transcript — user should rotate them.
- **1.5 fix** — Anthropic default model set to cheapest `claude-haiku-4-5` (user pref). Fixed a
  model-leak bug: the factory's single global `LLM_MODEL` default (qwen) leaked into all providers.
  Now each adapter owns its `DEFAULT_MODEL` (ollama qwen2.5:0.5b / anthropic claude-haiku-4-5) and
  the factory reads a **provider-specific** env `{PROVIDER}_MODEL` (computed key, still no branching);
  unset → adapter default. Verified all three resolutions.
- **1.6** — Extracted generic `common/registry.py::ProviderRegistry` (Generic[T], lazy loader,
  register/get/names); repointed `llm/registry.py` at it (same public API). New `embeddings/`
  package mirroring llm/: `ports.py` (`Embedder` Protocol: provider/model/dimensions +
  embed(list)→list[list] + embed_query), `adapters/ollama.py` (`OllamaEmbedder`, bge-m3, 1024-dim,
  `@register_embedder("ollama")`, httpx /api/embed batch), `factory.py` (`build_embedder`,
  EMBEDDING_PROVIDER/{PROVIDER}_EMBEDDING_MODEL). Pulled `bge-m3` (~1.2GB). **Paid embedder =
  eval-gated** (earliest Phase 5, realistic Phase 9) — only if recall@5 < 0.90; adding one is ~20min
  via the Port. Verified real semantic search (query shares no words with the matched refund chunk).
  **PHASE 1 COMPLETE** — data models + LLM Port + Embeddings Port, all real tools, no fakes.
  **Decisions:** Price = NOT a DB model (static reference data → Pydantic price book in code, 1.5);
  cost = computed + snapshotted on LLMCall (immutable receipt survives price changes);
  `LLMResponse` = Pydantic (1.5, Port return type); broker (RabbitMQ/Redis) is transport, `Job` is
  durable state — complementary, both needed (broker wired Phase 2). Verified all three via shell.
