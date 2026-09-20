"""Unit tests for the Sentence-Based chunker + its segmentation helper.

Pure functions, no DB/Django. Run inside the container:

    docker compose exec web python -m unittest chunkers.tests.test_sentence -v
"""

from __future__ import annotations

import unittest

from chunkers.adapters.sentence import SentenceChunker, split_sentences


class SplitSentencesTests(unittest.TestCase):
    def test_basic_three_sentences(self):
        text = "The refund is easy. Shipping takes five days! Is that clear?"
        self.assertEqual(
            split_sentences(text),
            ["The refund is easy.", "Shipping takes five days!", "Is that clear?"],
        )

    def test_abbreviation_not_split(self):
        text = "Dr. Smith signed the form. He approved it."
        self.assertEqual(
            split_sentences(text),
            ["Dr. Smith signed the form.", "He approved it."],
        )

    def test_decimal_not_split(self):
        text = "The rate is 3.14 percent today. It rose since then."
        self.assertEqual(
            split_sentences(text),
            ["The rate is 3.14 percent today.", "It rose since then."],
        )

    def test_arabic_question_mark_splits(self):
        text = "هل يمكنني استرداد أموالي؟ نعم خلال ثلاثين يوماً."
        parts = split_sentences(text)
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].endswith("؟"))

    def test_empty_returns_empty(self):
        self.assertEqual(split_sentences("   \n  "), [])


class SentenceChunkerTests(unittest.TestCase):
    def test_chunks_are_whole_sentences(self):
        chunker = SentenceChunker(chunk_size=40, overlap_sentences=0)
        text = "Refund is easy. Shipping is fast. Warranty is long."
        sentences = set(split_sentences(text))
        for c in chunker.chunk(text):
            # every sentence in a chunk is a complete original sentence
            for s in split_sentences(c.text):
                self.assertIn(s, sentences, msg=f"partial sentence: {s!r}")

    def test_size_bound_respected(self):
        chunker = SentenceChunker(chunk_size=45, overlap_sentences=1)
        text = "Alpha one two. Beta three four. Gamma five six. Delta seven eight."
        for c in chunker.chunk(text):
            self.assertLessEqual(len(c.text), 45, msg=repr(c.text))

    def test_contiguous_ordinals(self):
        chunker = SentenceChunker(chunk_size=30, overlap_sentences=0)
        text = "One sentence here. Two sentence here. Three sentence here."
        chunks = chunker.chunk(text)
        self.assertEqual([c.ordinal for c in chunks], list(range(len(chunks))))

    def test_sentence_overlap_repeats_a_sentence(self):
        chunker = SentenceChunker(chunk_size=35, overlap_sentences=1)
        text = "First short one. Second short one. Third short one."
        chunks = chunker.chunk(text)
        self.assertGreater(len(chunks), 1)
        # the last sentence of chunk k reappears as the first of chunk k+1
        prev_last = split_sentences(chunks[0].text)[-1]
        next_first = split_sentences(chunks[1].text)[0]
        self.assertEqual(prev_last, next_first)

    def test_oversized_sentence_hard_sliced_and_reconstructs(self):
        chunker = SentenceChunker(chunk_size=10, overlap_sentences=0)
        text = "x" * 25 + "."  # one very long "sentence"
        chunks = chunker.chunk(text)
        self.assertTrue(all(len(c.text) <= 10 for c in chunks))
        self.assertEqual("".join(c.text for c in chunks), text)


if __name__ == "__main__":
    unittest.main()
