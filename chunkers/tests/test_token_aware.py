"""Unit tests for the Token-Aware chunker.

The token windowing is pure (`window_ids`) and tested with plain lists. The chunker is
tested with a FakeTokenizer (words as tokens) so tests need no model download. Run:

    docker compose exec web python -m unittest chunkers.tests.test_token_aware -v
"""

from __future__ import annotations

import unittest

from chunkers.adapters.token_aware import TokenAwareChunker, window_ids


class FakeTokenizer:
    """Whitespace tokenizer: one token per word. encode/decode are exact inverses."""

    def encode(self, text: str) -> list[str]:
        return text.split()

    def decode(self, ids: list[str]) -> str:
        return " ".join(ids)

    def count(self, text: str) -> int:
        return len(text.split())


class WindowIdsTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(window_ids([], 4, 1), [])

    def test_no_overlap_exact_tiling(self):
        self.assertEqual(window_ids([1, 2, 3, 4, 5, 6], 3, 0), [[1, 2, 3], [4, 5, 6]])

    def test_overlap_shares_tokens(self):
        self.assertEqual(window_ids([1, 2, 3, 4, 5], 3, 1), [[1, 2, 3], [3, 4, 5]])

    def test_no_redundant_tail_window(self):
        # last window reaches the end -> we stop, no tiny duplicate tail
        self.assertEqual(window_ids([1, 2, 3, 4], 3, 1), [[1, 2, 3], [3, 4]])


class TokenAwareChunkerTests(unittest.TestCase):
    def setUp(self):
        self.chunker = TokenAwareChunker(
            chunk_tokens=3, overlap_tokens=0, tokenizer=FakeTokenizer()
        )

    def test_token_count_is_real_and_bounded(self):
        chunks = self.chunker.chunk("one two three four five six seven")
        for c in chunks:
            self.assertIsNotNone(c.token_count)
            self.assertLessEqual(c.token_count, 3)
        # 7 words, size 3, no overlap -> 3 + 3 + 1
        self.assertEqual([c.token_count for c in chunks], [3, 3, 1])

    def test_contiguous_ordinals(self):
        chunks = self.chunker.chunk("a b c d e f g h")
        self.assertEqual([c.ordinal for c in chunks], list(range(len(chunks))))

    def test_text_reconstructs_without_overlap(self):
        text = "alpha beta gamma delta epsilon zeta"
        chunks = self.chunker.chunk(text)
        self.assertEqual(" ".join(c.text for c in chunks), text)

    def test_empty_returns_empty(self):
        self.assertEqual(self.chunker.chunk("   "), [])


if __name__ == "__main__":
    unittest.main()
