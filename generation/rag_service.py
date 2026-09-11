"""
generation/rag_service.py  —  the full RAG loop (the thing that finally ANSWERS).

    question
      -> retrieve (whatever strategy the factory built: naive/hybrid/+rerank)
      -> build grounded prompt (lost-in-the-middle reorder + anti-hallucination rules)
      -> LLM answers
      -> return answer + the citations it was allowed to use

This service ORCHESTRATES only (thin): it holds a Retriever and an LLMClient and
wires them. All the real logic lives in the pieces it calls — clean layering.

The returned Answer carries the citations separately so the UI/eval can check the
answer against its allowed sources (faithfulness).
"""

from __future__ import annotations

from dataclasses import dataclass

from generation.context import SYSTEM_PROMPT, build_user_prompt
from llm.client import LLMClient
from retrieval.base import Retriever, RetrievedChunk


@dataclass
class Answer:
    text: str
    citations: list[str]            # "file, p.N" strings the answer may draw on
    chunks: list[RetrievedChunk]    # the raw retrieved chunks (for eval/debug)
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class RagService:
    def __init__(self, retriever: Retriever, llm: LLMClient, top_k: int = 5,
                 temperature: float = 0.0) -> None:
        self.retriever = retriever
        self.llm = llm
        self.top_k = top_k
        self.temperature = temperature

    def answer(self, question: str) -> Answer:
        # 1) retrieve
        chunks = self.retriever.retrieve(question, self.top_k)

        # 2) honest short-circuit: nothing retrieved -> don't even call the LLM.
        #    (No context = the model could only hallucinate. Refuse instead.)
        if not chunks:
            return Answer(
                text="I don't know based on the provided documents.",
                citations=[], chunks=[], model="(no-retrieval)",
            )

        # 3) build the grounded prompt
        user_prompt = build_user_prompt(question, chunks)

        # 4) ask the LLM (temperature 0 = deterministic, grounded)
        resp = self.llm.complete(SYSTEM_PROMPT, user_prompt, temperature=self.temperature)

        # 5) return the answer + the citations it was allowed to use
        citations = []
        for c in chunks:
            cit = c.citation()
            if cit not in citations:
                citations.append(cit)
        return Answer(
            text=resp.text,
            citations=citations,
            chunks=chunks,
            model=resp.model,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
        )