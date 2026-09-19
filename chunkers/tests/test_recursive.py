"""Unit tests for the Recursive chunker — a pure function, so no DB/Django needed.

Run inside the container (stdlib unittest; we deliberately haven't added pytest yet):

    docker compose exec web python -m unittest chunkers.tests.test_recursive -v
"""

from __future__ import annotations

import unittest

from chunkers.adapters.recursive import RecursiveCharacterChunker


class RecursiveChunkerTests(unittest.TestCase):
    def test_empty_or_whitespace_returns_no_chunks(self):
        chunker = RecursiveCharacterChunker(chunk_size=50, overlap=0)
        self.assertEqual(chunker.chunk(""), [])
        self.assertEqual(chunker.chunk("   \n\n  "), [])

    def test_ordinals_are_contiguous(self):
        chunker = RecursiveCharacterChunker(chunk_size=20, overlap=0)
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
        chunks = chunker.chunk(text)
        self.assertGreater(len(chunks), 1)
        self.assertEqual([c.ordinal for c in chunks], list(range(len(chunks))))

    def test_no_chunk_exceeds_chunk_size(self):
        chunker = RecursiveCharacterChunker(chunk_size=25, overlap=5)
        text = ("The refund policy is simple. You can get your money back. "
                "Shipping takes five days. The warranty lasts two years.")
        for c in chunker.chunk(text):
            self.assertLessEqual(len(c.text), 25, msg=repr(c.text))

    def test_does_not_split_words_midway(self):
        # With a space separator, boundaries fall between words, never inside one.
        chunker = RecursiveCharacterChunker(chunk_size=12, overlap=0)
        text = "alpha beta gamma delta epsilon"
        words = set(text.split())
        for c in chunker.chunk(text):
            self.assertTrue(
                all(w in words for w in c.text.split()),
                msg=f"a word was split: {c.text!r}",
            )

    def test_prefers_paragraph_boundary(self):
        # Two paragraphs, each fits alone but not together -> split on the blank line.
        chunker = RecursiveCharacterChunker(chunk_size=40, overlap=0)
        text = "First paragraph here.\n\nSecond paragraph here."
        chunks = chunker.chunk(text)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].text, "First paragraph here.")
        self.assertEqual(chunks[1].text, "Second paragraph here.")

    def test_oversized_single_token_is_hard_sliced(self):
        # A word with no separators, longer than chunk_size, must still be bounded.
        chunker = RecursiveCharacterChunker(chunk_size=10, overlap=0)
        text = "x" * 35
        chunks = chunker.chunk(text)
        self.assertTrue(all(len(c.text) <= 10 for c in chunks))
        self.assertEqual("".join(c.text for c in chunks), text)

    def test_overlap_carries_context_between_chunks(self):
        chunker = RecursiveCharacterChunker(chunk_size=20, overlap=8)
        text = "one two three four five six seven eight nine ten"
        chunks = chunker.chunk(text)
        self.assertGreater(len(chunks), 1)
        # Each chunk still respects the size bound even with the overlap seed.
        for c in chunks:
            self.assertLessEqual(len(c.text), 20)


if __name__ == "__main__":
    unittest.main()
