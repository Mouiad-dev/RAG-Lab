# RAG Lab ↔ AI Engineer Track — tool map

> Cross-reference between **this project's build phases** (`PLAN_1.md` / `PROGRESS.md`) and the
> **"AI Engineer Track 2026"** learning roadmap (`~/Downloads/ai-engineer-roadmap (2).html`).
> Purpose: at each RAG Lab step, learn the *right* Track tool for that step.

## ⚠️ The two numbering systems DO NOT match — always translate

RAG Lab **Phase 2** (ingestion/chunkers) is **NOT** Track **Phase 2** (that's *Tool calling & MCP*).
The RAG core maps to Track **Phase 4 — "Embeddings & RAG in production."** Never pull tools by the
matching number; use the table below.

## 🔴 Working rule (user decision, 2026-09-19)

**Hand-build everything for the entire project. Do NOT adopt any Track framework/tool mid-build.**
Frameworks are learned *about* at each step (so we know what they'd do), but we implement by hand
(Track Rule 01: "from scratch first"). **After the whole project is finished**, we run a dedicated pass
to try and compare the real tools against our hand-built versions. Even generic testing stays on the
stdlib / Django test runner until then.

## The map

| RAG Lab phase | Track phase | Tools to learn (adopt only in the post-project pass) | Status |
|---|---|---|---|
| P0 foundations | SWE base | Docker Compose, Postgres | ✅ done, hand-wired |
| P1 data model + LLM/Embeddings Ports | **P1** + **P4** | Anthropic SDK, Pydantic, **pgvector**; `instructor` (→ RAG-Lab P4) | ✅ done |
| **P2 ingestion + chunkers ← current** | **P4 (RAG)** | chunking **by hand**; refs: NirDiamant/RAG_Techniques, *Hands-On LLMs* book; LlamaIndex splitters = learn-about, deferred | 🔨 in progress |
| P2 async queue | P6–7 orchestration | Redis, Celery (Temporal = heavier cousin) | ✅ done |
| P3 retrieval (naive→hybrid, rerank) | **P4** | BM25, rerankers (BGE/Cohere), RAG_Techniques | ⬜ |
| P4 generation + citations | **P1** | `instructor` / Pydantic structured output | ⬜ |
| P5 eval harness | **P7** | RAGAS, LLM-as-judge | ⬜ |
| P6 prompt/context + caching | **P5** | prompt caching, context compression | ⬜ |
| P6b observability | **P5/P7** | Langfuse, Arize Phoenix, Prometheus | ⬜ |
| P7 tool calling | **P2** | tool schemas, function calling | ⬜ |
| P8 Axis-3 architectures | **P4 adv / P6** | CRAG, GraphRAG, multimodal (OCR), agentic | ⬜ |
| P8b memory | **P5** | Mem0, Zep, Letta | ⬜ |
| P9 hardening + CI eval gate | **P7** + senior CI/CD | eval-in-CI, guardrails (Guardrails AI / NeMo / Presidio) | ⬜ |
| P10 MCP server | **P2** | mcp SDK, FastMCP, OAuth 2.1, MCP Inspector | ⬜ |

## Learn-links (Track Phase 4, our current shelf)

- pgvector — https://github.com/pgvector/pgvector
- RAG_Techniques (one notebook per technique) — https://github.com/NirDiamant/RAG_Techniques
- LlamaIndex (deferred framework) — https://docs.llamaindex.ai/
- *Hands-On Large Language Models* — Alammar & Grootendorst (embeddings/chunking intuition)
- RAG vs CAG — https://www.datacamp.com/blog/rag-vs-cag
