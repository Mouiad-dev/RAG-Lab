# PRODUCT.md — RAG Lab / Document Intelligence Platform

> **Step 1 · "Shaping the build."** This file is written **before any code exists.**
> It defines *what* we are building and what *good* means — as measurable numbers —
> so that every later step (especially the eval suite in Step 8) has a finish line to race toward.
>
> Rule of this file: **a goal you cannot measure is just a wish.** Every claim below is a number
> or a yes/no, never an adjective like "fast" or "accurate."

---

## 1. Who is the user?

**Primary user: a compliance / legal-operations analyst** at a mid-size financial or legal firm.

- They live inside long, dense, badly-formatted PDFs: contracts, regulatory filings, policy
  handbooks, financial reports.
- They are **bilingual (Arabic + English)** and their documents mix both languages, sometimes on
  the same page.
- They are **accountable**: if they cite the wrong clause to a regulator or a client, there are
  real consequences. A confident wrong answer is worse to them than "I don't know."

> **Note on the dev domain vs. this brief.** Day-to-day development and learning happen against
> *manga + technical books* — free, fun, and they throw every hard case at us at once (image-heavy
> pages, tables, Arabic + English). But this brief is deliberately written for the **business user
> above**, because the business scenario is what sets *serious targets* and a *senior interview
> story*. We build cheap; we aim at the business bar.

---

## 2. What job does it do for them? (the one-sentence job)

> **"Given a pile of my own documents, answer my question in plain language and show me the exact
> page it came from — or tell me it doesn't know, rather than guess."**

The **citation** ("show me the exact page") and the **honest refusal** ("tell me it doesn't know")
are not nice-to-haves. For an accountable user they are the *entire point*. An answer they cannot
verify is worthless; an invented answer is dangerous.

**In scope:** ask a question in Arabic or English → get a grounded answer + a citation to the
source page → be able to say "I don't know" when the documents don't contain the answer.

---

## 3. What does "good enough" mean? (measurable targets)

These four numbers are the finish line. **In Step 8 they become the pass/fail thresholds of the
eval suite, and in the CI pipeline they become the merge gate.** They are written here, once,
so that "did this technique help?" always has a numeric answer later.

| Dimension | Target | Measured how | Why this number |
|---|---|---|---|
| **Faithfulness (anti-hallucination)** | **≥ 0.95** | RAG-Triad groundedness on the 30-question golden set | Accountable user; a made-up clause is the worst outcome. Highest bar in the file. |
| **Answer relevance** | **≥ 0.90** | RAG-Triad answer-relevance on the golden set | The answer must address the actual question, not an adjacent one. |
| **Retrieval quality** | **recall@5 ≥ 0.90** | fraction of golden questions whose correct chunk is in the top 5 retrieved | Retrieval is where RAG fails first (Step 6). Measured *separately* from the LLM. |
| **Latency** | **p95 ≤ 5 s** | end-to-end, question → answer, 95th percentile | A slow legal search doesn't get used. p95 (not average) so the unlucky user is protected. |
| **Cost** | **≤ $0.05 / question** at the demo tier | (input + output + rerank) token cost per answered question | Decides whether this can launch at all. Default dev runs on local models = $0. |

**"Good enough" in one sentence:** *on the 30-question golden set, cite the correct source page in
at least 9 of every 10 answers (recall@5 ≥ 0.90, faithfulness ≥ 0.95), each answer in under 5
seconds (p95), for under 5 cents.*

### What is too slow / too expensive (the red lines)
- **Too slow:** any single answer over **15 s** is treated as a failure, not a slow success.
- **Too expensive:** anything over **$0.15 / question** on the demo tier means the current
  strategy is disqualified regardless of accuracy — go back to a cheaper strategy.

---

## 4. MVP vs. careful build (the product judgment)

**This product leans careful, not rough — and here is the why.**

For most consumer features the right move is "ship rough, learn from users." Not here: the user is
**accountable**, so a wrong-but-confident answer causes real harm. The cost of being wrong is
higher than the cost of being late. Therefore:

- **MVP (ship first, learn):** English + Arabic Q&A over plain-text/markdown docs, hybrid
  retrieval, citations, and an honest "I don't know." This is enough to put in front of a test
  user and get real questions back.
- **Deliberately deferred until an eval proves we need it** (careful, not premature):
  GraphRAG, Multimodal/ColPali page-image retrieval, and Agentic multi-step retrieval. Each costs
  real latency + money (Step 6). We add them **only when the golden-set numbers demand it**, never
  because they're impressive.

> This is the Step 6 rule made concrete: *cheap-and-broad first (Hybrid + rerank), expensive-and-
> specific last, and only when a measurement — not a vibe — calls for it.*

---

## 5. Saying no (features deliberately NOT built)

Every feature costs tokens, latency, and complexity. These are **out of scope on purpose**:

- ❌ **Fine-tuning a model.** Retrieval + a good prompt hits the targets far cheaper. Revisit only
  if evals plateau below target with no retrieval fix left.
- ❌ **A "chat with 500 documents at once, no retrieval" mode.** This is the N² tax from Step 0.
  It's the anti-pattern the whole project exists to avoid.
- ❌ **Real-time document editing / write-back.** This is a *read + answer* tool, not an editor.
- ❌ **Multi-tenant accounts, billing, SSO.** Out of scope for the lab; it's a capability demo,
  not a SaaS launch.
- ❌ **Every embedding provider under the sun.** One good multilingual embedder (BGE-M3) behind an
  interface. Swappable, but not a zoo.

---

## 6. Trade-offs I can defend out loud (interview practice)

Three decisions, each phrased as *"I chose X over Y because of cost / latency / privacy."*

1. **"I default all development to local models (Ollama + local embeddings) over the Claude API,
   because of cost.** Claude Pro is a chat subscription, not API credits — RAG needs a separate
   paid key. So every experiment runs at $0 locally; only the final demo spends real money."

2. **"I made hybrid search (dense + BM25) mandatory rather than dense-only, because of accuracy on
   Arabic.** Arabic costs ~3× the tokens (the 'Arabic tax') and dense embeddings can smear literal
   Arabic terms; BM25 catches the exact keyword the analyst typed. For a bilingual accountable
   user, keyword recall isn't optional."

3. **"I wrote my own thin LLM Port + per-provider Adapter over adopting LangChain/LiteLLM as a code
   abstraction, because of control.** A framework couples me to *its* abstraction — I can't use a
   new provider feature (prompt caching, reasoning tokens) until the framework supports it. Explicit
   over implicit; no tight coupling. (LiteLLM may still appear later as an ops gateway, not as my
   code's abstraction.)"

---

## 7. How this file connects forward

```
PRODUCT.md (this file)  ──defines the numbers──▶  evals/golden_set + metrics (Step 8)
        │                                                        │
        │                                              run in CI as a merge gate
        │                                                        ▼
        └── every config/rag.yaml toggle (naive→hybrid→+rerank→+CRAG…) is judged
            "better or worse?" ONLY against the targets written here.
```

**Bottom line:** nothing downstream is "done" until it hits the Section 3 numbers. This file is the
finish line; the rest of the roadmap is the race.

---

*Written before a single line of application code, per Step 1 of the roadmap. Committed as the first
box in the flagship pipeline.*