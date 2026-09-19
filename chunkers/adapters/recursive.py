"""Recursive character chunker — the workhorse that beats blind fixed-cut.

The idea (the same one LlamaIndex's node parsers and LangChain's
RecursiveCharacterTextSplitter implement — we build it by hand, Track Rule 01):
instead of cutting every N characters, break at the most NATURAL boundary that
keeps a piece under the size limit, walking down a hierarchy of separators:

    "\\n\\n"  paragraph   ->  "\\n"  line   ->  ". "/"! "/"؟ " sentence
                          ->  " "  word     ->  ""  character (last resort)

Split on the coarsest separator present; any piece still over `chunk_size` is
split again by the NEXT separator down (that's the "recursive" part). Then adjacent
small pieces are merged back up toward `chunk_size` with overlap, so we don't emit
hundreds of fragments. Result: chunks that respect paragraph/sentence/word
boundaries and only hard-slice when a single token is genuinely too long.

Arabic sentence punctuation (؟ ، !) is in the separator list so AR text breaks at
real boundaries too (bilingual recall target).
"""

from __future__ import annotations

from ..ports import ChunkData
from ..registry import register_chunker

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 200

# Coarse -> fine. "" is the last resort (split into characters). Separators are kept
# attached to their piece so concatenation reconstructs the text exactly.
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "؟ ", "! ", "، ", " ", ""]


@register_chunker("recursive")
class RecursiveCharacterChunker:
    strategy = "recursive"

    def __init__(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
        separators: list[str] | None = None,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= overlap < chunk_size:
            raise ValueError("overlap must be >= 0 and < chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separators = separators or DEFAULT_SEPARATORS

    # --- step 1: recursively break text into small "atoms" (each <= chunk_size) ---
    def _split(self, text: str, separators: list[str]) -> list[str]:
        # Pick the coarsest separator that actually occurs in this text.
        separator = separators[-1]
        remaining: list[str] = []
        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                remaining = []
                break
            if sep in text:
                separator = sep
                remaining = separators[i + 1 :]
                break

        if separator == "":
            parts = list(text)  # last resort: characters
        else:
            raw = text.split(separator)
            # Re-attach the separator to every piece but the last, so the pieces
            # concatenate back to the original text (no lost whitespace/newlines).
            parts = [p + separator for p in raw[:-1]] + [raw[-1]]

        atoms: list[str] = []
        for part in parts:
            if not part:
                continue
            if len(part) <= self.chunk_size:
                atoms.append(part)
            elif remaining:
                atoms.extend(self._split(part, remaining))  # recurse finer
            else:
                # A single token longer than chunk_size: hard-slice as last resort.
                for j in range(0, len(part), self.chunk_size):
                    atoms.append(part[j : j + self.chunk_size])
        return atoms

    # --- step 2: greedily merge atoms into chunks up to chunk_size, with overlap ---
    def _merge(self, atoms: list[str]) -> list[str]:
        chunks: list[str] = []
        current = ""
        for atom in atoms:
            if current and len(current) + len(atom) > self.chunk_size:
                chunks.append(current)
                tail = current[-self.overlap :] if self.overlap else ""
                # Only carry the overlap tail if it still leaves room for `atom`.
                current = tail if len(tail) + len(atom) <= self.chunk_size else ""
            current += atom
        if current.strip():
            chunks.append(current)
        return chunks

    def chunk(self, text: str) -> list[ChunkData]:
        text = text.strip()
        if not text:
            return []

        merged = self._merge(self._split(text, self.separators))
        chunks: list[ChunkData] = []
        for piece in merged:
            piece = piece.strip()
            if not piece:
                continue
            chunks.append(
                ChunkData(
                    text=piece,
                    ordinal=len(chunks),  # contiguous 0..n-1 even if a piece was dropped
                    metadata={
                        "strategy": self.strategy,
                        "chunk_size": self.chunk_size,
                        "overlap": self.overlap,
                    },
                )
            )
        return chunks
