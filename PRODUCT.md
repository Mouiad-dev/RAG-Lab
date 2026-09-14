# RAG Lab — PRODUCT.md (the finish line)

> Written **before any code**. This file defines what "good" means as **numbers**.
> Every later decision is settled by measurement against these targets, not taste.
>
> 🔴 **The one rule:** never add a technique until an eval proves it improves a number here.

---

## What the product is

A document question-answering system: a user uploads documents into a **notebook**, asks
questions in Arabic or English, and gets a **grounded answer with a citation to the exact
source page** — or an honest **"I don't know"** when the documents don't contain the answer.

It is also an **engineering lab**: every retrieval/generation technique is a config switch,
an eval harness scores any configuration against the targets below, and CI blocks any change
that lowers a score.

## Who the user is (this sets the quality bar)

A **compliance / legal-operations analyst** — accountable, bilingual (Arabic + English), and
punished for citing the wrong clause.

> For this user, a **confident wrong answer is worse than "I don't know."**

This single fact is why **faithfulness and citations are non-negotiable**, and why the system
must be willing to abstain.

*(Development uses free manga + tech-book PDFs, but the targets below are written for this
serious user.)*

## The measurable targets (the finish line)

| Dimension | Target | Why it matters |
|---|---|---|
| **Faithfulness** (grounded, not invented) | **≥ 0.95** | accountable user; hallucination is the worst outcome |
| **Answer relevance** | **≥ 0.90** | it must answer the actual question asked |
| **Retrieval recall@5** | **≥ 0.90** | retrieval fails first; measured separately from the answer |
| **p95 latency** | **≤ 5 s** | a slow legal search simply doesn't get used |
| **Cost / question** | **≤ $0.05** | decides if it can launch; **$0 in dev** on local models |

## Red lines (automatic failure)

- Any single answer taking **> 15 s** = failure.
- Any strategy costing **> $0.15 / question** = disqualified.

## How these targets shape the build (forward references)

- `p95 ≤ 5 s` and the 20-files × 50 MB scale ⟶ **ingestion must be async** (task queue).
- `cost ≤ $0.05` ⟶ **prompt/KV caching** and **model routing** (cheap model for grading).
- `recall@5 ≥ 0.90` on bilingual text ⟶ **hybrid (dense + keyword) search** is mandatory.
- `faithfulness ≥ 0.95` ⟶ **"answer only from context, else say I-don't-know"** + validated citations.
- All of it ⟶ **eval harness + eval-in-CI** so no regression ever ships.
