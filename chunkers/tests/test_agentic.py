"""Unit tests for the Agentic chunker.

Pure parse/group logic tested directly; the chunker tested with a FakeLLM (canned JSON),
so no network/spend. The deterministic fallback is exercised by a FakeLLM returning junk.

    docker compose exec web python -m unittest chunkers.tests.test_agentic -v
"""

from __future__ import annotations

import unittest

from chunkers.adapters.agentic import (
    AgenticChunker,
    group_by_boundaries,
    parse_boundaries,
)
from llm.fakes import FakeLLM


class ParseBoundariesTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_boundaries('{"breakpoints": [1, 3]}', 5), [1, 3])

    def test_prose_around_json_tolerated(self):
        raw = 'Sure! Here you go: {"breakpoints": [0, 2]} hope that helps'
        self.assertEqual(parse_boundaries(raw, 4), [0, 2])

    def test_out_of_range_and_last_index_dropped(self):
        # 9 is out of range; 3 (== n-1) is a meaningless trailing break -> dropped
        self.assertEqual(parse_boundaries('{"breakpoints": [1, 9, 3]}', 4), [1])

    def test_non_increasing_deduped(self):
        self.assertEqual(parse_boundaries('{"breakpoints": [2, 2, 1]}', 6), [2])

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            parse_boundaries("not json at all", 5)


class GroupTests(unittest.TestCase):
    def test_groups_split_after_breakpoints(self):
        sentences = ["a.", "b.", "c.", "d."]
        self.assertEqual(
            group_by_boundaries(sentences, [1]),
            ["a. b.", "c. d."],
        )

    def test_no_breaks_single_group(self):
        self.assertEqual(group_by_boundaries(["a.", "b."], []), ["a. b."])


class AgenticChunkerTests(unittest.TestCase):
    def test_uses_llm_breakpoints(self):
        text = "Refund topic one. Refund topic two. Space topic one. Space topic two."
        llm = FakeLLM(text='{"breakpoints": [1]}')  # split after sentence 1
        chunks = AgenticChunker(llm=llm).chunk(text)
        self.assertEqual(len(chunks), 2)
        self.assertFalse(chunks[0].metadata["fallback"])
        self.assertIn("Refund topic two", chunks[0].text)
        self.assertIn("Space topic one", chunks[1].text)

    def test_falls_back_on_garbage(self):
        text = "One here. Two here. Three here."
        llm = FakeLLM(text="lol no json")  # unparseable -> deterministic fallback
        chunks = AgenticChunker(llm=llm).chunk(text)
        self.assertTrue(all(c.metadata["fallback"] for c in chunks))
        self.assertEqual([c.ordinal for c in chunks], list(range(len(chunks))))

    def test_empty_returns_empty(self):
        self.assertEqual(AgenticChunker(llm=FakeLLM()).chunk("  "), [])


if __name__ == "__main__":
    unittest.main()
