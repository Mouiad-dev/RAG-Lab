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
