"""
evals/runner.py  —  THE LAB. Run the golden set against a config, get numbers.

This is what makes "did technique X help?" answerable. It:
  1. loads the golden set (the exam),
  2. builds the retriever the config asks for (naive / hybrid / +rerank),
  3. for each question: retrieves, measures recall@k + latency; optionally runs
     the RAG loop + LLM-judge for faithfulness/answer_relevance,
  4. aggregates into a scorecard and checks each number against PRODUCT.md targets.

The whole point: run this with retrieval.mode: naive, then hybrid, then +rerank
-> compare scorecards -> the delta justifies the technique. Same exam every time.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.repository import DocumentRepository
from embeddings.embedder import Embedder
from evals.metrics import LLMJudge, percentile, recall_at_k
from generation.rag_service import RagService
from retrieval.factory import build_retriever


@dataclass
class GoldenItem:
    id: str
    question: str
    expected_source: str
    expected_pages: list[int]
    lang: str = "en"


def load_golden_set(path: str | Path) -> list[GoldenItem]:
    items = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        items.append(GoldenItem(
            id=d["id"], question=d["question"],
            expected_source=d["expected_source"],
            expected_pages=d["expected_pages"], lang=d.get("lang", "en"),
        ))
    return items


@dataclass
class Scorecard:
    mode: str
    n: int
    recall_at_k: float
    p95_latency_s: float
    mean_latency_s: float
    faithfulness: float | None = None       # None = not measured (no LLM judge)
    answer_relevance: float | None = None
    per_question: list[dict] = field(default_factory=list)

    def check(self, thresholds: dict) -> dict[str, bool]:
        """Compare each measured number to its PRODUCT.md target (pass/fail)."""
        out = {
            "recall_at_5": self.recall_at_k >= thresholds.get("recall_at_5", 0.90),
            "p95_latency": self.p95_latency_s <= thresholds.get("p95_latency_seconds", 5.0),
        }
        if self.faithfulness is not None:
            out["faithfulness"] = self.faithfulness >= thresholds.get("faithfulness", 0.95)
        if self.answer_relevance is not None:
            out["answer_relevance"] = self.answer_relevance >= thresholds.get("answer_relevance", 0.90)
        return out


class EvalRunner:
    def __init__(self, cfg: dict, repo: DocumentRepository, embedder: Embedder) -> None:
        self.cfg = cfg
        self.repo = repo
        self.embedder = embedder

    def run(
        self,
        golden: list[GoldenItem],
        top_k: int = 5,
        rag_service: RagService | None = None,   # provide to also score answer quality
        judge: LLMJudge | None = None,           # provide to score faithfulness/relevance
    ) -> Scorecard:
        retriever = build_retriever(self.cfg, self.repo, self.embedder)
        mode = self.cfg.get("retrieval", {}).get("mode", "naive")

        recalls: list[float] = []
        latencies: list[float] = []
        faiths: list[float] = []
        rels: list[float] = []
        per_q: list[dict] = []

        for item in golden:
            t0 = time.perf_counter()
            hits = retriever.retrieve(item.question, top_k)
            dt = time.perf_counter() - t0
            latencies.append(dt)

            pages = [h.page_number for h in hits if h.source_filename == item.expected_source]
            r = recall_at_k(pages, item.expected_pages)
            recalls.append(r)

            row = {"id": item.id, "lang": item.lang, "recall": r,
                   "latency_s": round(dt, 3),
                   "retrieved_pages": [h.page_number for h in hits]}

            # optional: full answer quality via the RAG loop + LLM judge
            if rag_service is not None and judge is not None:
                ans = rag_service.answer(item.question)
                context = "\n\n".join(c.text for c in ans.chunks)
                f = judge.faithfulness(context, ans.text)
                a = judge.answer_relevance(item.question, ans.text)
                faiths.append(f); rels.append(a)
                row["faithfulness"] = round(f, 3)
                row["answer_relevance"] = round(a, 3)

            per_q.append(row)

        return Scorecard(
            mode=mode,
            n=len(golden),
            recall_at_k=sum(recalls) / len(recalls) if recalls else 0.0,
            p95_latency_s=round(percentile(latencies, 95), 3),
            mean_latency_s=round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
            faithfulness=(sum(faiths) / len(faiths)) if faiths else None,
            answer_relevance=(sum(rels) / len(rels)) if rels else None,
            per_question=per_q,
        )