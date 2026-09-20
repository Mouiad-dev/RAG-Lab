# AI Learning Log

> Updated after every sub-step. Each entry: what was taught, why it matters, the pattern used.
> This is the "learning" half of the project — the code proves the concept; this explains it.

---

## Phase 0 — Foundations & the finish line

### Step 0.1 — Define the finish line before code (`PRODUCT.md`)

**Concept.** Decide what "good" means as **numbers** before building anything. Like marking a
race's finish line before you start running. Without it, every choice ("add reranking?") is
opinion; with it, every choice becomes a measurement ("did the number improve?").

**Why first.** It's free, near-permanent, and it *shapes the architecture*: the p95≤5s target
forces async ingestion later; cost≤$0.05 forces caching; recall@5≥0.90 on bilingual text forces
hybrid search. Build the targets first or build the wrong shape and rework it.

**Design pattern.** None — deliberately. This is **product sense**, not code. Naming "no pattern"
honestly is part of the discipline.

**The targets set:** faithfulness ≥0.95, answer relevance ≥0.90, recall@5 ≥0.90, p95 ≤5s,
cost ≤$0.05/question. Red lines: >15s = failure, >$0.15/q = disqualified. User = accountable
bilingual compliance analyst, for whom a confident wrong answer is worse than "I don't know."

**Also set up:** `PROGRESS.md` (in-repo tracker so any new session resumes instantly) and this
learning log.

### Step 0.2 — The smallest Django project that boots

**Concept.** Pour the concrete slab before building rooms. `django-admin startproject config .`
gives four files: `settings.py` (all config), `urls.py` (the router), `wsgi.py`/`asgi.py` (the
entry points a server calls). `manage.py` is the command runner. That's the entire skeleton —
no RAG, no models, no apps yet.

**Why now.** Docker (0.3) needs a real project to run; it can't run nothing. Building the
skeleton *outside* Docker first gives a 1-second feedback loop (`manage.py check`) instead of a
slow image rebuild — prove it's sound, then containerize.

**Design pattern.** Still minimal, but we set the layout convention the plan's architecture
(§6) hangs on: a thin `config/` package for settings; app/service/repository code will live in
separate packages added later. Fat models, thin views — enforced by *where* code goes.

**Dependency discipline.** A dep is added the step it's first used and pinned exactly
(Django==5.2.17 LTS, psycopg[binary]==3.3.5). psycopg is pulled in now because Postgres arrives
in 0.3/Phase 1; SQLite is a temporary stand-in only so the skeleton boots with zero services.

**Verified:** `python manage.py check` → "System check identified no issues".

### Step 0.3 — The whole dev stack as one system (docker-compose)

**Concept.** `docker compose up` starts several containers as one system with one command.
We declared three: **db** (`pgvector/pgvector:pg16` — Postgres with the pgvector extension
baked in, our vector store), **ollama** (local LLM + embeddings, $0, no host install), and
**web** (the Django app built from our Dockerfile). They share a private network and reach
each other by *service name*: web → `db:5432`, web → `http://ollama:11434`.

**Why now.** Phase 1 needs a real Postgres+pgvector to store embedding vectors — SQLite can't
do vector search. The DB must exist before we write models. Proving all three boot and see
each other is the milestone that says "the system is wired," not just one app.

**Design pattern.** Infrastructure-as-code: the environment is declared, versioned, and
reproducible. **Every image is pinned** (pg16, ollama 0.34.0, python 3.13-slim) so
"works on my machine" can't happen. Config comes from env vars (`.env`) so the *same*
`settings.py` runs on the host and in compose — 12-factor style.

**Two real-world snags fixed (worth remembering):**
1. A Docker **named volume remembers the Postgres major version** that first initialized it.
   The old v1 volume was pg17; our pinned pg16 refused to start ("data directory initialized
   by version 17"). Fix: since it was discardable dev data, remove the volume and let pg16
   init fresh. Lesson: pin the DB major version *and* don't reuse another version's data dir.
2. `depends_on` alone only waits for *start*, not *ready*. We add a **healthcheck**
   (`pg_isready`) and `condition: service_healthy` so web doesn't race a not-yet-accepting DB.

**Verified:** inside `web`, `manage.py migrate` applied on pg16 (real connection), and
`urlopen('http://ollama:11434/api/version')` → `{"version":"0.34.0"}`.

### Step 0.4 — The health endpoint (first real code path)

**Concept.** One tiny URL, `/health/`, that actively asks "can I reach my dependencies right
now?" and answers in JSON. It bakes the manual proof from 0.3 (migrate, urlopen) into the app
so anyone — Docker, CI, a load balancer — can ask "is it alive?" with a single request.

**Why now.** It's the first end-to-end path through Django (URL → view → DB + Ollama → JSON),
and it closes Phase 0's official done test: "a health check confirms DB + Ollama reachable."

**Design pattern (first taste of §6 layering).** **Thin view**: the view only orchestrates —
it calls `_check_database()` / `_check_ollama()` helpers and serializes the result; it holds
no business logic. A deliberately small preview of Controller → Service. Also: correct HTTP
semantics — **200 only if all deps ok, else 503** — so monitoring tools act on the status code,
not by parsing a body.

**Gotcha learned.** Django's test `Client` uses host `testserver`, which isn't in
`ALLOWED_HOSTS`; pass `HTTP_HOST="localhost"` (or add testserver) or you get an HTML 400 instead
of your JSON.

**Verified BOTH paths (not just the happy one):** healthy → 200
`{"status":"ok",...}`; Ollama pointed at a dead port → 503
`{"status":"unhealthy", "checks":{"database":"ok","ollama":"error: ...Connection refused"}}`.
Proving the failure path matters — a health check that can't go red is theater.

---

## ✅ Phase 0 complete — foundations & the finish line are in place.

---

## Phase 1 — Data model (ORM) + LLM/Embeddings Ports

### Step 1.1 — Teach Postgres what a vector is (enable pgvector)

**Concept.** Postgres knows numbers/text/dates but not "vector" (a list of ~1024 floats that
encodes *meaning*). The **pgvector** extension adds a `vector` column type plus distance
operators (`<=>` cosine, `<->` L2, `<#>` inner product) — the machinery of semantic search. The
image ships the extension *files*, but you must turn it on in the DB with one statement:
`CREATE EXTENSION IF NOT EXISTS vector;`. Until then, a `vector` column errors with "type vector
does not exist."

**Why first in Phase 1.** The `Chunk` model (1.3) has a `vector` field that literally cannot be
created until the extension is on. So this is the true first brick.

**Design pattern.** *Migrations as versioned schema history* — schema is code, applied in order,
reproducible on any fresh DB (yours, a teammate's, CI's). Django provides a first-class op,
`django.contrib.postgres.operations.CreateExtension("vector")`, so no raw SQL and it's reversible.
Note: enabling the extension is NOT the "one quarantined raw fragment" (the `<=>` search) — Django
has a native operation for it, so we stay ORM-clean here.

**Structure choice.** New `documents` app owns the RAG domain (Document, Chunk, ...), separate
from `core` (cross-cutting glue like health). Its migration `0001` is *only* the extension, so
"vector support" is the base all model migrations build on. Kept `models.py` empty — atomic steps.

**Verified:** `pg_extension` shows `vector` v0.8.6; `'[1,2,3]'::vector` casts successfully.

### Step 1.2 — The Document model + the Repository pattern

**What a Document is.** The "library index card" for one uploaded file: structured *facts about*
the file (title, collection, content_type, language, page_count, size, status, timestamps) plus a
pointer to the actual bytes. It is NOT the bytes themselves.

**Where the bytes live (the storage decision).** Three options weighed: (1) in Postgres as
`bytea` — rejected, it bloats the DB and streams slowly; DBs are for structured data + vectors,
not fat blobs. (2) Filesystem via a mounted volume — chosen for now: simple, $0, fast; the DB row
stores only the *path*. (3) S3/MinIO — the production answer, deferred to Phase 9. The clean
trick: Django's `FileField` + a separate `STORAGES` setting means switching disk→S3 later is a
*config change, not a code change* (same Port/Adapter spirit as the LLM). Rule: **structured data
+ vectors in Postgres, fat bytes in cheap object storage.**

**The Repository pattern (the "one counter clerk").** Problem: scattering `Document.objects.
filter(...)` across many files means any query change (or swapping in vector search) forces edits
everywhere, and tangles business logic with DB details. Fix: put ALL database talking for a domain
in ONE place — a repository with named methods (`create`, `get`, `list_in_collection`). Everyone
else asks the repository; nobody touches `Document.objects` directly. Benefits: (a) query changes
live in one file; (b) 🔴 the ugly-but-necessary raw pgvector `<=>` search gets *quarantined* in
`ChunkRepository.search_by_vector` (1.3) while everything else stays clean ORM — the repository is
*why* we can keep the plan's ORM promise; (c) tests can swap a fake repository to check their own
logic without a real DB. (Repository = writes; "Selector" = reads — kept as one class for now, KISS.)

**Fat model vs thin view.** Behavior about *one* object → a model method (`document.mark_ready()`).
Talking to the DB about *many* objects → the repository. Coordinating steps → service/view. The
model knows how to change *itself*; it doesn't run queries about its siblings.

**Verified:** via the container shell, `repo.create(...)` saved a Document (id + file on the
`/app/media` volume), `repo.get()` read it back, `mark_ready()` persisted `status=ready`, and
`list_in_collection("notebook")` returned it — all against real Postgres. Confirmed the row in
`documents_document` via psql, then cleaned up.

### Step 1.3 — The Chunk model + the quarantined vector search

**What a Chunk is.** A small slice of a document's text (a "sticky-note excerpt") plus its
embedding vector, linked back to its Document and source `page` (which becomes the citation). We
can't feed a whole 50-page PDF to the LLM per question (N² attention tax, cost, noise), so we cut
docs into chunks and search only the few nearest ones.

**Embeddings, plainly.** An embedding is a list of ~1024 numbers encoding *meaning*; similar
meaning → geometrically close vectors. We embed the question the same way and ask the DB "which
chunk vectors are closest?" — so "money-back" can match "refund" without sharing words. The
dimension is FIXED (BGE-M3 = 1024) and must match at index-time and query-time, or distances are
meaningless. Kept as one constant `EMBEDDING_DIM`; changing embedders => migration + re-embed.

**Storing vectors is clean; searching is the honest part.** The `pgvector` Python lib gives a
Django `VectorField` (clean ORM to store). But nearest-neighbor search needs pgvector's `<=>`
cosine operator, which has NO plain ORM syntax. 🔴 So we quarantine it in ONE method,
`ChunkRepository.search_by_vector`, using pgvector's `CosineDistance("vector", query)` annotation
+ `.order_by("distance")`. This stays ORM-native and parameterized (no raw string, no injection),
and everywhere else stays pure ORM. The Repository pattern is exactly what makes this containment
possible. Also: **pre-filter by collection** (never post-filter) for precision + Notebook/Golden
isolation.

**Deferred deliberately.** The ANN index (HNSW/IVFFlat) that keeps search fast at scale is left as
a marked NOTE — exact search is fine for a few hundred chunks; add the index when it earns its
place (measure first = the one rule).

**Verified (allowed test-double, not a forbidden fake).** Real embedder isn't wired until 1.6, so
we tested *our storage + search logic* with hand-made 1024-dim vectors: A(=query)=0.0000 <
C(near)=0.0061 < B(orthogonal)=1.0000 — correct nearest-first ranking on REAL pgvector. Real
embeddings will flow through this identical code path from 1.6 on.

### Step 1.4 — The lab's memory of itself (Job, GoldenQuestion, LLMCall)

Three small tables that hold structured records (not documents), split by concern into apps.

**`Job` vs a message broker (RabbitMQ/Redis) — different layers, both needed.** A broker is a
*pipe* that delivers a task message to a worker (transport); its messages vanish once consumed. A
`Job` is a durable Postgres *row* that records status (queued→extracting→chunking→embedding→ready/
failed) so the UI can show live progress and failures survive a crash. You can't query an in-flight
broker message for "60% done," and a table can't dispatch work — so: broker moves work, Job records
truth. Built the model now (Phase 1 = data); the Celery+Redis worker that writes it comes Phase 2.
Job is a fat-model state machine (transition methods set started_at/finished_at).

**`LLMCall` + the DB-vs-Pydantic rule (the important lesson).**
- **DB model** = something you persist and query, one row per record/event, unbounded growth
  (Document, Chunk, Job, LLMCall, GoldenQuestion).
- **Pydantic model** = a typed object flowing through code in memory — a boundary shape, a config,
  a validated response (LLMResponse, an Answer, the price book). Not stored as rows.
- Applied: usage and money are **split** into two DB rows (1:1): `LLMCall` = USAGE (tokens,
  latency, model, purpose) and `CallCost` = MONEY (a **breakdown**: input/output/cache_write/
  cache_read/total, currency, `price_ref`). Both written together in one transaction; the dollar
  amounts are **computed + snapshotted** (Decimal, not float) so historical costs survive price
  changes. Splitting earns its place only *because* it's a breakdown + price snapshot, not a lone
  column (a 1:1 for one number would be over-engineering). Option A: every call always gets a
  CallCost ($0 for Ollama). Cache is modeled on both sides: usage has cache_creation (write) +
  cache_read tokens; cost has cache_write_cost + cache_read_cost.
- **Price is NOT a DB model** (user decision + right call): prices are static reference data that
  live with the code → a Pydantic/dict **price book** (added 1.5), read to *compute* cost. A DB
  migration to change a price would be wrong.
- **Cost is not a model at all** — it's a function (tokens × price), result stored on LLMCall.
- **PromptTemplate** (versioned prompt asset) is a real DB model but deferred to Phase 2/4 when
  prompts exist; for now `LLMCall.prompt_ref` is a string pointer like `"answer@v1"`.

This sequencing means: the LLM **adapters** (1.5) return a Pydantic `LLMResponse`, compute cost via
the price book, and write an `LLMCall` receipt — so cost is logged uniformly no matter the backend.

**Verified:** GoldenQuestion saved; Job walked queued→ready (progress 100, both timestamps set);
two LLMCalls logged each with a CallCost (Ollama $0; Anthropic breakdown 0.0003+0.0009+0.0003=
0.0015), `total_cost()` aggregated to $0.0015, CASCADE delete removed both rows. All real Postgres.

### Step 1.5a — The LLM boundary: your own type, a Protocol, and the price book

**Two kinds of "model."** `LLMResponse` and `ModelPrice` are **Pydantic** models — typed objects
in memory, validated, not DB rows. `LLMCall`/`CallCost` are **DB** models — rows you persist.
Knowing which is which is the core skill here.

**`LLMClient` as a `typing.Protocol` (structural typing).** A Protocol declares the *shape*
(`provider`, `model`, `complete(...) -> LLMResponse`); any object with that shape *is* an
LLMClient — no base class, no inheritance. `@runtime_checkable` lets `isinstance(x, LLMClient)`
check method presence. This is the Port: Ollama, Anthropic, and the test Fake all satisfy it, so
we swap providers by config. "No vendor type escapes the adapter" — results are mapped into our
own `LLMResponse` before crossing the boundary, so services/models/views never see anthropic.* or
Ollama dicts.

**The price book is Pydantic, not a DB table (deliberate).** Prices are static reference data
that live with the code — git history is the price history, no migration to read them, no DB
dependency inside a pure calculation. `ModelPrice` IS the "price model" the user asked for; it's
just in-memory. Promote to a DB table only if runtime-editable prices are ever needed. `compute_cost`
turns token usage → a `CostBreakdown` (input/output/cache-write/cache-read/total + `price_ref`),
and we snapshot those dollars onto CallCost so history survives price changes.

**Real 2026 Anthropic rates** (snapshot 2026-06-24, per 1M tokens): Opus 5 $5/$25, Sonnet 5
$2/$10, Haiku 4.5 $1/$5; cache-write ≈1.25× input, cache-read ≈0.1× input. Ollama = $0.

**Test doubles live in `llm/fakes.py` (TEST-ONLY).** FakeLLM proves *our* logic without spend —
allowed by the no-fakes rule precisely because it tests our code, not the product.

**Verified:** `isinstance(FakeLLM(), LLMClient)` is True; Haiku 1M in/out/cache-read = $1/$5/$0.10
= $6.10; Sonnet 1200-in/150-out = $0.0039; Ollama = $0.

### Step 1.5b — Real Ollama adapter + the metering Decorator + the Factory

**Adapter (Port/Adapter).** `OllamaClient` makes a real HTTP call (httpx → `/api/chat`,
`stream=False`) and maps Ollama's response fields (`prompt_eval_count` → input_tokens,
`eval_count` → output_tokens, `done_reason` → stop_reason) into our `LLMResponse`. No Ollama dict
escapes the file. Base URL from `OLLAMA_BASE_URL` (works on host and in compose).

**Metering (Decorator pattern).** `MeteredLLMClient` wraps *any* LLMClient: same interface (so it's
itself an LLMClient), adds one behavior — after the inner call it computes cost via the price book
and writes the `LLMCall`+`CallCost` receipt — then returns the response. Because logging lives in
the decorator, not each adapter, "log usage/cost on EVERY call" is enforced in ONE place regardless
of backend. This is the same shape we'll reuse for a caching decorator later (Phase 6).

**Factory + registry (no if/else — open/closed).** Instead of `if provider == "ollama": ...`, each
adapter is a **Strategy** that self-registers under a key via `@register_provider("ollama")`. The
**Factory** (`build_llm_client`) reads `LLM_PROVIDER`/`LLM_MODEL` and does a polymorphic registry
lookup (`get_provider_builder(provider)`), then wraps the result in metering. Adding a provider =
write an adapter + one decorator + one import line in `adapters/__init__.py`; the factory itself
never changes. `_ensure_adapters_loaded()` lazily imports the adapter package on first lookup so the
registry is always populated regardless of call order (function-level import avoids a circular
import, since adapters import the registry at their top). This is Protocol + Strategy + Factory +
polymorphism working together — the "flip a switch" spine.

**Verified (real, no fakes):** `build_llm_client(provider="ollama")` → a real generation ("Paris is
the capital of France.", 30/8 tokens) and the decorator auto-wrote a $0 `LLMCall`+`CallCost` with
`price_ref` stamped. First call ~7.5s because Ollama loads the model into memory — warm calls are
far faster; not a real p95 sample.

### Step 1.5c — The Anthropic adapter (real SDK) + the payoff of the pattern

**One more Strategy, zero factory edits.** `AnthropicClient` is just another
`@register_provider("anthropic")` adapter — proof the registry design pays off: the factory didn't
change at all to gain a whole new provider. It flows through the same `MeteredLLMClient`, so an
Anthropic call writes a **real-dollar** CallCost (unlike Ollama's $0), computed from the price book.

**Step-1 discipline baked in (§5b).** Explicit timeout; **check `stop_reason`** — raise
`TruncatedResponseError` on `max_tokens` and `RefusalError` on `refusal` (a truncated/refused reply
is never shipped as if valid). Map the SDK's `usage` (incl. cache tokens) into our `LLMResponse`;
no `anthropic.types.*` escapes the adapter.

**Modern Claude models reject `temperature`** (Opus 5 / Sonnet 5 etc. → HTTP 400 on sampling
params). The adapter accepts the `temperature` kwarg (to satisfy the Protocol) but does not forward
it; determinism is the model default. This is a real 2026 API constraint worth remembering.

**Real-world gotcha:** an **org-scoped** API key returns 400 "not scoped to a workspace" — either
send an `anthropic-workspace-id` header (supported via `ANTHROPIC_WORKSPACE_ID`) or use a
**workspace-scoped** key. Failed 400s are not billed.

**Verified (real charge):** haiku call → 'Paris', 22/4 tokens, and a real receipt of $0.000042
(22×$1/M input + 4×$5/M output) written by the same decorator. Same code path as Ollama, different
price. **Phase 1's LLM spine is done.**

### Step 1.6 — The Embeddings Port + the first real semantic search

**Embedder = twin of the LLM Port.** LLM: text → text. Embedder: text → a 1024-number vector
(fingerprint of meaning). Same `Protocol + Strategy + Factory + registry` shape. `Embedder` declares
`embed(list)`/`embed_query(one)` + `provider/model/dimensions`. `OllamaEmbedder` calls bge-m3 via
`/api/embed`.

**BGE-M3:** 1024-dim (= `EMBEDDING_DIM`, so it drops into `Chunk.vector`), multilingual (AR+EN),
$0 on Ollama. The dimension must match at index and query time — the "same embedder both times" rule.

**DRY win — the generic `ProviderRegistry`.** Instead of copy-pasting the LLM registry, extracted one
`common/registry.py::ProviderRegistry(Generic[T])` with a lazy `loader`. Both `llm/registry.py` and
`embeddings/registry.py` are now thin instances of it; the same class will power the chunker,
retriever, and RAG-architecture registries (Axes 1–3). One engine, many switches.

**When do we adopt a paid embedder?** Eval-gated, not scheduled. BGE-M3 stays default unless an eval
(earliest Phase 5) shows recall@5 < 0.90; realistic swap point is Phase 9 (demo/deploy). Because of
the Port, adding a `VoyageEmbedder` later is ~20 min + a config line — never a rewrite. That's the
payoff of building the interface now.

**Verified — the whole point of RAG, made real:** embedded 3 real sentences (1024-dim each), stored
them as real `Chunk`s, then queried *"how can I get my money back?"* — nearest hit was the **refund**
sentence (dist 0.358) despite sharing **no words** with it, well ahead of the vacation/HQ chunks
(~0.59). Real bge-m3 + real pgvector, no hand-made numbers.

---

## ✅ Phase 1 complete — data models + LLM Port + Embeddings Port. All real tools, no fakes.
The retrieval foundation is live: real documents/chunks in pgvector, a provider-swappable LLM with
cost receipts, and a real multilingual embedder producing vectors that search by meaning.

---

## Phase 2 — Ingestion pipeline + AXIS 1 (chunkers) + async queue

### Step 2.1 — The ingestion assembly line (synchronous vertical slice)

**Concept.** Ingestion is an assembly line that turns a raw file into searchable rows:
`extract → chunk → embed → store`. Until now we had all the *parts* (Document, Chunk, a real
embedder, the Job state machine) but nothing that *ran the line*. Step 2.1 builds the whole line and
runs it **synchronously** (in-process, blocking) on a small file — the point is to prove the stages
connect and the output is correct *before* adding hard things on top.

**Why synchronous first, when Phase 2's headline is "async"?** Two hard things at once is where bugs
hide. If you wrap an unproven pipeline in Celery and it breaks, you can't tell whether the *pipeline*
or the *queue* is wrong. So 2.1 = prove the pipeline when called directly; 2.2 = move the *same
function* behind Celery+Redis so it runs in the background with live Job updates. **The pipeline body
doesn't change between them — only who calls it and from where.** That's the whole reason the queue is
a separate step.

**Design patterns, and why each is here:**
- **Pipeline** — discrete ordered stages; the orchestrator (`ingest_document`) advances the `Job`
  state machine *between* stages (`mark_extracting → mark_chunking → mark_embedding → ready/failed`).
  Those fat-model Job methods, dormant since 1.4, finally do their job. (Progress is coarse now; it
  becomes *live* and meaningful once async in 2.2.)
- **Strategy + Port/Adapter** — the `Chunker` is a Protocol (`strategy` + `chunk(text) -> list[ChunkData]`),
  exactly like `LLMClient`/`Embedder`. The pipeline depends on the *interface*, so flipping the
  `CHUNKER` env swaps the algorithm with zero pipeline edits. `FixedSizeChunker` is the first strategy.
- **Factory + the GENERIC `ProviderRegistry`** — the third reuse of `common/registry.py`. `build_chunker`
  is ~10 lines and contains no `if/else`; adding a chunker = one adapter + one decorator + one import.
  This is the concrete payoff of extracting the generic registry back in 1.6 — a whole new axis for ~15 lines.
- **Repository** — all DB access stays in the repos; the pipeline holds orchestration only. The store
  step is `transaction.atomic()` **clear-then-insert**, which makes re-ingest *idempotent* (the
  `unique(document, ordinal)` constraint would otherwise clash on a second run) and prevents a crash
  mid-store from leaving half a document.

**A typed boundary, again (`ChunkData`).** A chunker returns our OWN Pydantic `ChunkData` list, not
Django `Chunk` rows — the same "no vendor/DB type escapes the boundary" discipline as `LLMResponse`.
The chunker is pure text-in/data-out and never touches the ORM; the *pipeline* maps `ChunkData → Chunk`
rows and embeds them. This is what lets a chunker be unit-tested with no database at all.

**Fixed-Size = the honest baseline, deliberately naive.** It slides a fixed-width **character** window
with an **overlap** (so a sentence straddling a boundary survives in a neighbour). It knows nothing
about sentences/paragraphs/structure — PLAN_1.md's rule is "never blind fixed-cut," so this is the
baseline we will *measure and beat* with recursive/semantic/structure-aware chunkers later. Two honesty
choices: it **breaks when a window already reaches the end** (no redundant near-duplicate tail chunk),
and `token_count` stays **None** rather than faking a number — a real tokenizer arrives with a later
chunker (char-length ≠ tokens; presenting an estimate as a count would be a fake).

**The extractor is a seam, not the feature.** 2.1's `extract_text` handles the **text path only**
(txt/markdown → UTF-8) and raises `UnsupportedContentError` for a PDF/image. That's enough to exercise
the full four-stage line honestly, and it makes the deferred **router** (text-PDF vs image→OCR) a single
obvious place to branch later — nothing up or downstream changes when OCR bolts on.

**Failures are recorded, not swallowed.** Any stage error marks BOTH the Document and the Job `failed`
with the reason, then **re-raises** so the caller/worker sees it. A pipeline that hides failures is as
useless as a health check that can't go red (0.4's lesson, applied to ingestion).

**Verified (real, no fakes):** a 5-line policy file → extract → Fixed-Size chunk → **real bge-m3**
embed → 5 embedded `Chunk` rows in pgvector; the Job walked `queued→…→ready` (progress 100, both
timestamps set). A semantic query *"how do I get a reimbursement?"* — sharing **no words** with the
text — ranked the **Refund** chunk nearest (0.473). Re-ingesting with a *different* chunk config
replaced the chunks cleanly (idempotent, no unique clash). An unsupported PDF drove the failure path:
`UnsupportedContentError`, Document + Job both `failed`, error surfaced. Test rows cleaned up.

**What 2.1 intentionally is NOT:** no Celery/queue (2.2), no chunkers 2–8 (2.3+), no PDF/OCR router,
no auto-advisor, no upload UI. One small, proven slice — then we add each hard thing on top of a green base.

### Step 2.2 — Move ingestion into the background (Celery + Redis)

**Concept.** A 50 MB PDF can't be ingested inside an HTTP request — the browser would time out and one
upload would tie up a web worker. So the slow work moves off the request path onto a **task queue**:
the web process just drops "ingest doc 7" onto a queue and returns instantly; a separate **worker**
process does the actual pipeline. This is the **Producer–Consumer** pattern, with three roles:
- **Producer** — the web process (here, the management command). Enqueues a task, returns immediately.
- **Broker (Redis)** — the pipe that holds task messages until a worker is free. Messages are transient.
- **Consumer (Celery worker)** — a long-running process that pulls tasks and runs `ingest_document`.

**The `Job` vs broker distinction, now real (callback to 1.4).** The broker *moves* the work
(transient — gone once consumed); the `Job` Postgres row *records the truth* (durable — survives
restarts, and is what a UI polls for live progress). You can't ask an in-flight Redis message "how far
along?"; you ask the `Job`. That's why we built `Job` in Phase 1 and only wired the broker now — they're
complementary layers, not alternatives.

**Why the pipeline body didn't change (the whole point of splitting 2.1/2.2).** The Celery task is a
THIN wrapper: `@shared_task` → call the exact `ingest_document` from 2.1. All 2.2 adds is *who calls it
and from where*. Because 2.1 was already proven correct when called directly, anything that breaks in 2.2
is queue plumbing, not pipeline logic. Same "a task/tool is a thin adapter over a service, zero business
logic inside" rule we'll reuse for tool calling in Phase 7.

**Producer creates the Job, not the pipeline.** The command creates `Job(queued)` and returns its id
*before* enqueuing, so status is queryable the instant the request returns (models the real upload
handler: create Job → return id to the browser → worker processes). The worker's pipeline reuses that
Job via `latest_for_document`.

**Design patterns:** Task Queue / Producer–Consumer (core); broker-vs-durable-state (Redis + Job);
**same-image-different-command** (the `worker` service reuses the web image, just runs `celery … worker`
instead of `runserver` — infra reuse, one build).

**Reliability knobs worth knowing.** `task_time_limit` = a hard ceiling so a task can't run forever
(🔴 the same "always bound the loop" discipline as agent `max_turns`). `acks_late` +
`reject_on_worker_lost` = a task is acknowledged only *after* it finishes, so if a worker dies mid-run
the task is **redelivered** rather than silently lost. That redelivery is only safe because 2.1's store
step is **idempotent** (clear-then-insert) — a re-run can't duplicate chunks. The two steps compose:
2.1's idempotency is what lets 2.2 choose the safer delivery mode. This also partly compensates for
Redis-as-broker being less durable than RabbitMQ (the Phase-9 upgrade path).

**Why Redis now, RabbitMQ later.** Redis is one small container that *also* becomes our cache in Phase 6,
so it earns its keep twice; RabbitMQ is the stronger *broker* (durable queues, publisher confirms, acks)
but it's broker-only and adds AMQP concepts while we're focused on the queue pattern itself. Our durable
backstop is the `Job` row, so the simpler broker is safe. Because Celery abstracts the broker, switching
is a `broker_url` change + one compose service — deferred to Phase 9, *if* ingestion reliability demands
it. (Same "build the interface, defer the heavy tool until it earns its place" discipline as the
eval-gated paid embedder.)

**Real-world gotcha (Postgres password).** Recreating the containers surfaced an auth failure:
`POSTGRES_PASSWORD` only sets the password when the data volume is **first initialized** — afterwards
it's ignored. The `pgdata` volume had been initialized with an older password than `.env`'s current
`test2026`; the long-running containers had masked the mismatch by holding the old value in their
environment. Fix was non-destructive: `ALTER USER rag PASSWORD 'test2026'` to align the volume with
`.env`. Lesson: the **volume**, not the env var, is the source of truth for an already-initialized DB.

**Verified (real, no fakes):** enqueue returned in ~1s with `Job#4 queued` + a task id, while the
**separate worker container** received the task, embedded via Ollama, and drove the Job to `ready`
(worker log: `received → POST /api/embed 200 → succeeded {'state':'ready'}`); the semantic query still
found the Refund chunk. The first worker embed took ~23s (cold bge-m3 load in the fresh process) — a real
reminder that a cold worker's p95 ≠ warm p95. Warm runs complete `queued→…→ready` in well under a second.

**What 2.2 intentionally is NOT:** no retry/backoff or dead-letter tuning yet (Phase 9), no upload HTTP
view / live-status UI (comes with the web layer), no RabbitMQ (Phase 9 if needed). One proven async slice.

### Step 2.3 — Recursive chunking (respect boundaries, hand-built)

**Concept.** Fixed-Size cuts at a blind character count, so it slices mid-word/mid-sentence
(`"...money back wit" | "hin thirty days..."`). Recursive chunking cuts at the most **natural boundary
that still fits** the size limit, walking a *hierarchy of separators* from coarse to fine:
paragraph `\n\n` → line `\n` → sentence `. `/`؟ `/`! ` → word ` ` → character `` (last resort). Split on
the coarsest separator present; any piece still over `chunk_size` is split again by the *next* separator
down (the "recursive" part); a single token longer than the limit is hard-sliced only as a last resort.
Then adjacent small pieces are **merged back up** toward `chunk_size` with an overlap tail. Arabic
sentence punctuation is in the list so AR text breaks at real boundaries too (bilingual recall).

**Why this one, and why by hand.** It's the industry workhorse (what LlamaIndex node parsers /
LangChain's `RecursiveCharacterTextSplitter` do) and the biggest practical jump over the baseline. Per the
AI Engineer Track's **Rule 01 ("from scratch first")** and the user's decision to **hand-build the entire
project and only evaluate real frameworks in a final pass**, we implemented it ourselves — no LlamaIndex,
no new dependency. Even the test uses the **stdlib `unittest`** rather than adding pytest (a tool is a tool).

**Design pattern — the switch, finally exercised.** Recursive is just another **Strategy** behind the same
`Chunker` Port: one new adapter + `@register_chunker("recursive")` + one import line. The pipeline, factory,
task, and worker did not change at all. `build_chunker(strategy="recursive")` (or `CHUNKER=recursive`) flips
it. This is the first time we *prove* the registry pays off with a second real strategy — the whole reason
the lab exists ("flip a switch, measure the difference").

**Two implementation subtleties worth remembering.** (1) Keep the separator **attached** to each split
piece so concatenation reconstructs the original text exactly — otherwise merges silently drop
newlines/spaces. (2) When seeding the next chunk with an overlap tail, **guard** that `tail + next_atom`
still fits `chunk_size`, or overlap can push a chunk over the limit. Ordinals are assigned from the count
of kept chunks, so they stay contiguous even if a piece is dropped as empty.

**Testing a pure function (new discipline).** A chunker is text-in/data-out — no DB, no network — so it's
the ideal first unit test. 7 cases: empty→`[]`, contiguous ordinals, size bound respected, **no mid-word
split**, **prefers the paragraph boundary**, oversized single token is hard-sliced *and* reconstructs
exactly, overlap keeps the size bound. This starts the suite the Phase-9 CI eval/merge gate will run.

**Track mapping (so we learn the right tool at the right time).** This step is AI Engineer Track **Phase 4
— Embeddings & RAG** (NOT Track Phase 2, which is MCP — the two numbering systems differ; see
`TRACK_MAP.md`). Tools to *learn about* here: LlamaIndex splitters (the framework we defer), and the
NirDiamant/RAG_Techniques repo + *Hands-On LLMs* book as references for the technique.

**Verified:** all 7 unit tests green; a side-by-side showed `fixed_size` splitting `wit|hin`/`acr|oss`
while `recursive` broke at word boundaries; and a real end-to-end ingest with `strategy="recursive"`
embedded + stored the chunks (`metadata.strategy=recursive`), Job `ready`, semantic search returned the
refund chunk. Registry now: `['fixed_size', 'recursive']`.

**What 2.3 intentionally is NOT:** Sentence/Semantic/Document-based/Token-aware/Agentic chunkers come one
at a time in 2.4+ (Token-aware is also when `token_count` stops being None — it needs a real tokenizer).
No framework adopted (deferred to the post-project tool pass).

### Step 2.4 — Sentence-Based chunking (the sentence is sacred)

**Concept.** Make the **sentence the atomic unit**: segment the text into sentences first, then pack whole
sentences into a chunk up to `chunk_size`, never ending mid-sentence. Optional **sentence-level overlap**
carries a sentence of context across the seam. Complete sentences embed more coherently and read cleanly as
citations.

**The distinction from Recursive (worth holding).** Recursive uses the sentence as one rung of a
*size-driven* ladder — it can still end partway through a sentence if that's what fits, and it doesn't
*know* what a sentence is (it only avoided splitting `Dr. Smith` in the demo because the merge step happened
to fit). Sentence-Based inverts the priority: the boundary is sacred, size is met by choosing *how many*
whole sentences. It's also the **prerequisite for Semantic chunking (#5)**, which groups these sentences by
embedding similarity — so 2.4 unlocks 2.5.

**Segmentation is the hard part (and where we're honest about limits).** Naïve `split(".")` breaks on
`Dr.`, `e.g.`, `3.14`, section numbers, URLs. Our hand-rolled `split_sentences()` splits on `[.!?؟]`+
whitespace but **re-joins across false boundaries** using a small guard: known abbreviations, a trailing
digit (decimals/`1.2`), and single-letter initials. **Bilingual:** Arabic ends with `؟`/`.`/`!` and has *no
capital letters*, so we rely on punctuation+whitespace, not a "then-Capital" rule. This regex has real gaps
— documented in the code — and the field tool (**spaCy `.sents` / NLTK punkt / LlamaIndex SentenceSplitter**)
is the upgrade we reserve for the **post-project tool pass**, per the hand-build-first rule.

**Pattern — the switch, a third time.** New adapter + `@register_chunker("sentence")` + one import; pipeline/
factory/task/worker untouched. Registry is now `['fixed_size', 'recursive', 'sentence']`. The new pure
helper (`split_sentences`) is unit-tested on its own — the value of keeping segmentation a pure function.

**Track mapping.** Still **Track Phase 4 (Embeddings & RAG)**. Tools to *learn about* this step: spaCy /
NLTK punkt (statistical sentence segmentation), LlamaIndex `SentenceSplitter` — all deferred frameworks.

**Verified:** 10 new unit tests (17 total in the chunker suite) all green; three-way side-by-side shows
`fixed_size` cutting `in 3|0` while `recursive`/`sentence` break clean; a real ingest with
`strategy="sentence"` produced whole-sentence chunks, embedded + stored, Job `ready`, semantic search found
the refund chunk.

**What 2.4 intentionally is NOT:** no spaCy/NLTK (post-project), and Semantic (#5, builds on this),
Document-based (#6), Token-aware (#7, needs a tokenizer → also unblocks real `token_count`), Agentic (#8)
each remain their own later sub-steps.

### Step 2.5 — Semantic chunking (cut where the meaning shifts)

**Concept.** Instead of size or punctuation, cut by **meaning**. Embed each sentence, measure the cosine
distance between neighbours, and place a boundary where the distance **spikes** — a topic change. A chunk
becomes one coherent topic. Steps: `split_sentences` (reuse 2.4) → embed all (BGE-M3, one batch) →
adjacent-pair distances → breakpoints where distance exceeds a **percentile** threshold (default 90th,
data-adaptive so it adjusts per document, not a magic absolute) → group → a `chunk_size` cap splits an
oversized coherent run.

**The design first: a chunker that needs the embedder.** Every prior chunker was pure text→data. Semantic
needs vectors to decide boundaries, so `SemanticChunker` takes an `Embedder` as a **constructor dependency**
(lazy `build_embedder()`), and the `Chunker` Port signature stays `chunk(text)` — the pipeline calls it
unchanged. Consequence I flagged honestly in code: sentences are **embedded twice** (here for boundaries,
again in the pipeline's store stage). Reusing them would couple the stages, so it's deferred.

**Keeping a pure, testable core out of a network-bound chunker.** The embedder makes this chunker
non-deterministic and Ollama-bound, so the decision logic is split into pure functions —
`cosine_distance` (hand-written dot/norm, no numpy), `_percentile`, and `find_breakpoints(distances, pct)`
— unit-tested with synthetic distance arrays and a **FakeEmbedder** (a test double is fine *inside a unit
test*; the no-fakes rule governs the product). The real embedding path is verified end-to-end.

**The honest trade-off — and why it points at Phase 5.** Semantic chunking gives topically-pure chunks, but
it embeds every sentence *at ingestion* (expensive) and the threshold is finicky and embedder-dependent.
Whether it actually beats Recursive/Sentence on recall is exactly what the **Phase-5 eval harness** will
measure — it's the textbook case of "measure, don't assume." It also reinforces the Track's *same-embedder*
rule: boundaries ride on the very BGE-M3 vectors we later search with.

**Pattern — the switch, a fourth time.** New adapter + `@register_chunker("semantic")` + one import;
everything else untouched. Registry now `['fixed_size', 'recursive', 'sentence', 'semantic']`.

**Track mapping.** Track **Phase 4**. Learn-about tool: **LlamaIndex `SemanticSplitterNodeParser`** (which
popularized this percentile-breakpoint method) — deferred to the post-project pass.

**Verified:** 10 new tests (27 total, all green); and a real run on a two-topic document (a refund policy
followed by James Webb telescope facts) put the boundary **exactly** at the topic shift — three refund
sentences in one chunk, three telescope sentences in the next — using real bge-m3, no size/punctuation cue.

**What 2.5 intentionally is NOT:** Document-based (#6), Token-aware (#7 → unblocks real `token_count`),
Agentic (#8) remain later; the "is it better?" measurement waits for the Phase-5 evals.

### Step 2.6 — Document-Based chunking (respect the doc's own structure)

**Concept.** Cut on the document's **own structure** — Markdown headings — not size/punctuation/embeddings.
Each heading (`#`/`##`/`###`) starts a section that stays intact; the **heading path** breadcrumb
(`Refund Policy › Timing`) rides in `metadata["heading_path"]`, which is a far better citation than a raw
offset. The plan's "v1 winner" because policies/contracts/manuals are heading-structured and humans cite
the section.

**Two patterns introduced here.** (1) **Composition** — Document-based delegates oversized sections to an
injected `body_chunker` (default recursive), so it stays focused on *structure* and reuses proven
*size*-splitting; the `Chunker` Port signature is unchanged (dependency injected, like the embedder in 2.5).
(2) **Graceful fallback** — a doc with *no headings* delegates wholesale to the fallback chunker instead of
emitting one giant chunk. Honest behavior: this strategy shines on structured docs and does the sensible
thing on plain text.

**The pure core.** `parse_sections(text)` (heading detection + a level-stack that computes the ancestor
path, popping deeper-or-equal levels on each new heading) is a pure function, unit-tested without embedder or
DB. Keeping the parser pure is what makes the tricky nesting logic verifiable in isolation.

**Track mapping.** Track **Phase 4**. Learn-about tools: LlamaIndex `MarkdownNodeParser`, LangChain
`MarkdownHeaderTextSplitter`, and — for extracting structure from real PDFs — Unstructured.io / LlamaParse
(the "Document AI" senior extension). All deferred. This step also foreshadows the deferred **PDF/OCR
extraction router**: once we parse PDFs, this same chunker consumes the headings they yield.

**Verified:** 9 new tests (36 total, all green); a real Markdown policy doc produced one chunk per section,
each carrying the correct heading_path, and a semantic query landed on the exact **Refund Policy › Timing**
section — the breadcrumb doubling as a citation.

**What 2.6 intentionally is NOT:** Token-aware (#7, needs a real tokenizer → unblocks real `token_count`)
and Agentic (#8, LLM decides the cuts) remain later sub-steps; real PDF heading *extraction* is the deferred
OCR router + post-project tool pass.
