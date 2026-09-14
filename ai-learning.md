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
