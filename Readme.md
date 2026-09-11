# RAG Lab — Document Intelligence Platform

A configurable RAG system where **every technique is a switch** you flip from a web
control panel, then measure. Built step by step alongside the AI Engineer roadmap.

> Start with [`PRODUCT.md`](./PRODUCT.md) — it defines "good" as numbers. Those
> numbers are the eval targets everything else races toward.

## Run it

```bash
cp .env.example .env          # set a real POSTGRES_PASSWORD
docker compose up --build     # boots db (pgvector) + ollama + app (Django)
```

Then pull the models into the ollama box (one time):
```bash
docker compose exec ollama ollama pull bge-m3      # embeddings (multilingual)
docker compose exec ollama ollama pull llama3.1:8b # the answer LLM
```

Open **http://localhost:8000** — the control panel.

## The control panel

Left rack = the config, live:
- **retrieval.mode**: naive · hybrid · query_transform · crag · graph · agentic
- **query_transform**: none · rewrite · hyde (shown when mode=query_transform)
- **top_k**: how many chunks to retrieve
- **rerank**: cross-encoder re-scoring on/off

Ask a question (Arabic or English). You get the grounded answer, its **citations**,
and an expandable view of the **exact chunks** used — so you can *see* how each
strategy changes the result. Flip a switch, ask again, compare.

## Ingesting your documents

The ingestion pipeline (extract → chunk → embed → store) lives in `ingestion/`.
Point it at a file and it routes automatically (text PDF → Docling/pdftotext,
image PDF/PNG → OCR). See `ingestion/service.py`.

## Measuring (the whole point)

`evals/` runs the golden set against any config and scores it vs PRODUCT.md targets
(recall@k, faithfulness, latency). Run naive, then hybrid, then +rerank → compare
the numbers → that delta justifies the technique. See `evals/runner.py`.

## Layout

```
config/rag.yaml   the switches (the heart)
ingestion/        extract → chunk → embed → store   (Phase A)
retrieval/        naive·hybrid·query_transform·crag·graph·agentic + rerank (Phase B)
generation/       grounded answer + citations + honest "I don't know"
evals/            golden set + metrics + runner (the lab)
core/             pgvector schema + repository (data layer)
llm/ embeddings/  Port+Adapter for LLM and embeddings (provider-swappable)
web/              Django control panel + chat UI
```