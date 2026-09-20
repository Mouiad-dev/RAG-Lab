"""Unit tests for the Semantic chunker.

The embedder-driven part is tested with a FAKE embedder (a test double is allowed inside
unit tests — the no-fakes rule is about the product, not the tests). The math
(cosine_distance, find_breakpoints) is pure and tested directly. Run:

    docker compose exec web python -m unittest chunkers.tests.test_semantic -v
"""

from __future__ import annotations

import unittest

from chunkers.adapters.semantic import (
    SemanticChunker,
    cosine_distance,
    find_breakpoints,
)


class FakeEmbedder:
    """Maps each sentence to a caller-supplied vector, by order."""

    def __init__(self, vectors):
        self._vectors = vectors

    def embed(self, texts):
        return [self._vectors[i] for i in range(len(texts))]


class CosineTests(unittest.TestCase):
    def test_identical_vectors_zero_distance(self):
        self.assertAlmostEqual(cosine_distance([1.0, 2.0], [1.0, 2.0]), 0.0, places=6)

    def test_orthogonal_vectors_distance_one(self):
        self.assertAlmostEqual(cosine_distance([1.0, 0.0], [0.0, 1.0]), 1.0, places=6)

    def test_zero_vector_is_max_distance(self):
        self.assertEqual(cosine_distance([0.0, 0.0], [1.0, 1.0]), 1.0)


class FindBreakpointsTests(unittest.TestCase):
    def test_no_distances_no_breaks(self):
        self.assertEqual(find_breakpoints([], 90), [])

    def test_spike_becomes_a_breakpoint(self):
        # one clear jump at index 2 -> boundary after sentence 2
        distances = [0.05, 0.04, 0.9, 0.05]
        self.assertEqual(find_breakpoints(distances, 90), [2])

    def test_uniform_distances_no_break(self):
        # all equal -> nothing strictly above the percentile
        self.assertEqual(find_breakpoints([0.2, 0.2, 0.2, 0.2], 90), [])


class SemanticChunkerTests(unittest.TestCase):
    def test_boundary_falls_between_two_topics(self):
        # sentences 0,1 = topic A; 2,3 = topic B (orthogonal vectors)
        sentences_text = "Aaa aaa. Aaa more. Bbb bbb. Bbb more."
        vectors = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]]
        chunker = SemanticChunker(
            chunk_size=1000, breakpoint_percentile=75, embedder=FakeEmbedder(vectors)
        )
        chunks = chunker.chunk(sentences_text)
        self.assertEqual(len(chunks), 2)
        self.assertIn("Aaa", chunks[0].text)
        self.assertNotIn("Bbb", chunks[0].text)
        self.assertIn("Bbb", chunks[1].text)

    def test_contiguous_ordinals(self):
        vectors = [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
        chunker = SemanticChunker(
            chunk_size=1000, breakpoint_percentile=50, embedder=FakeEmbedder(vectors)
        )
        chunks = chunker.chunk("One here. Two here. Three here.")
        self.assertEqual([c.ordinal for c in chunks], list(range(len(chunks))))

    def test_size_cap_splits_a_large_semantic_group(self):
        # all same topic (no semantic break) but over chunk_size -> size cap splits it
        vectors = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]
        chunker = SemanticChunker(
            chunk_size=20, breakpoint_percentile=90, embedder=FakeEmbedder(vectors)
        )
        chunks = chunker.chunk("Alpha alpha. Beta beta. Gamma gamma.")
        self.assertTrue(all(len(c.text) <= 20 for c in chunks))

    def test_empty_returns_empty(self):
        chunker = SemanticChunker(embedder=FakeEmbedder([]))
        self.assertEqual(chunker.chunk("   "), [])


if __name__ == "__main__":
    unittest.main()
