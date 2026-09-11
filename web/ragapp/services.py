"""
web/ragapp/services.py  —  the thin bridge between the UI and the RAG engine.

Views orchestrate only; this service builds the RAG pieces from a config dict that
merges the base rag.yaml with the LIVE overrides the user picked in the UI. That's
the whole point of the control panel: change retrieval.mode / rerank / etc. from a
form, and this rebuilds the retriever accordingly — the same build_retriever the
eval lab uses, so the UI and the evals always agree.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

import psycopg
import yaml

from core.repository import DocumentRepository
from embeddings.embedder import OllamaEmbedder
from generation.rag_service import RagService
from llm.client import build_llm
from retrieval.factory import build_retriever

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "rag.yaml"


def load_base_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _dsn() -> str:
    import os
    return (
        f"host={os.environ.get('POSTGRES_HOST','db')} "
        f"port={os.environ.get('POSTGRES_PORT','5432')} "
        f"user={os.environ.get('POSTGRES_USER','rag')} "
        f"password={os.environ.get('POSTGRES_PASSWORD','')} "
        f"dbname={os.environ.get('POSTGRES_DB','rag_lab')}"
    )


@lru_cache(maxsize=1)
def _connection() -> psycopg.Connection:
    # one long-lived connection for the app process; autocommit for simple reads.
    conn = psycopg.connect(_dsn(), autocommit=True)
    return conn


def merge_overrides(base: dict, overrides: dict) -> dict:
    """Return a deep copy of base with the UI's retrieval.* overrides applied."""
    cfg = copy.deepcopy(base)
    r = cfg.setdefault("retrieval", {})
    if "mode" in overrides:
        r["mode"] = overrides["mode"]
    if "top_k" in overrides:
        r["top_k"] = int(overrides["top_k"])
    if "query_transform" in overrides:
        r["query_transform"] = overrides["query_transform"]
    if "rerank_enabled" in overrides:
        r.setdefault("rerank", {})["enabled"] = bool(overrides["rerank_enabled"])
    if "graph_enabled" in overrides:
        r.setdefault("graph", {})["enabled"] = bool(overrides["graph_enabled"])
    if "agentic_enabled" in overrides:
        r.setdefault("agentic", {})["enabled"] = bool(overrides["agentic_enabled"])
    return cfg


def answer_question(question: str, overrides: dict) -> dict:
    """Build the configured RAG pipeline and answer one question. Returns a dict
    ready for JSON (answer, citations, chunks, the config actually used)."""
    base = load_base_config()
    cfg = merge_overrides(base, overrides)

    repo = DocumentRepository(_connection())
    embedder = OllamaEmbedder.from_yaml(cfg)
    llm = build_llm(cfg)

    retriever = build_retriever(cfg, repo, embedder, llm=llm)
    rag = RagService(retriever, llm, top_k=cfg["retrieval"].get("top_k", 5))
    ans = rag.answer(question)

    return {
        "answer": ans.text,
        "citations": ans.citations,
        "model": ans.model,
        "mode": cfg["retrieval"]["mode"],
        "rerank": cfg["retrieval"].get("rerank", {}).get("enabled", False),
        "chunks": [
            {"citation": c.citation(), "score": round(c.score, 4),
             "preview": c.text[:200]}
            for c in ans.chunks
        ],
        "tokens": {"prompt": ans.prompt_tokens, "completion": ans.completion_tokens},
    }