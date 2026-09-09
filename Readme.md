# RAG Lab — Document Intelligence Platform

A configurable RAG system where **every technique is an on/off switch** in one
config file. Flip a switch → re-run the same eval suite → measure the delta.
Built step by step alongside the AI Engineer roadmap.

> Start with [`PRODUCT.md`](./PRODUCT.md) — it defines what "good" means as
> numbers. Those numbers are the finish line every later step races toward.

## Current state: skeleton (the empty machine)

Three boxes that boot and talk to each other. No RAG logic yet.

| Box | Image | Role |
|---|---|---|
| `db` | `pgvector/pgvector:pg17-trixie` | Postgres that can store + search vectors |
| `ollama` | `ollama/ollama` | Local AI brain, $0 for dev |
| `app` | built from `Dockerfile` | Your code (runs `boot_check.py` for now) |

## Run it

```bash
cp .env.example .env          # then edit .env (set a real POSTGRES_PASSWORD)
docker compose up --build     # boots all three boxes
```

`app` runs `boot_check.py`, which proves it can:
1. read `config/rag.yaml`,
2. reach `db` and enable pgvector,
3. reach `ollama`,
4. see the eval targets.

Green **ALL CHECKS PASSED** = the foundation is solid.

## The heart

[`config/rag.yaml`](./config/rag.yaml) is where the lab happens. Everything else
is scaffolding that reads from it.

## Layout

```
config/      the on/off switches (the heart)
llm/         Port + Adapter — talk to any LLM the same way   (later box)
embeddings/  text -> multilingual meaning-vectors            (later box)
ingestion/   Phase A: upload -> extract -> chunk -> store     (later box)
retrieval/   Phase B: swappable strategies naive->hybrid->…   (later box)
evals/       golden set + metrics, judged vs PRODUCT.md       (later box)
core/        fat models, domain events, repositories          (later box)
web/         thin views + chat UI                             (later box)
```
Empty folders hold a `.gitkeep` until their box is built. Frame first.