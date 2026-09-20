"""Unit tests for the Document-Based chunker + its structure parser.

Pure function tests (parse_sections) plus the chunker. Run:

    docker compose exec web python -m unittest chunkers.tests.test_document -v
"""

from __future__ import annotations

import unittest

from chunkers.adapters.document import DocumentChunker, parse_sections


class ParseSectionsTests(unittest.TestCase):
    def test_headings_and_nesting_path(self):
        text = (
            "# Refund Policy\n"
            "You may request a refund.\n"
            "## Eligibility\n"
            "Items must be unused.\n"
            "## Timing\n"
            "Within 30 days.\n"
            "# Shipping\n"
            "Five business days."
        )
        sections = parse_sections(text)
        paths = [p for p, _ in sections]
        self.assertEqual(
            paths,
            [
                ["Refund Policy"],
                ["Refund Policy", "Eligibility"],
                ["Refund Policy", "Timing"],
                ["Shipping"],
            ],
        )
        # the heading line is kept in the section body
        self.assertTrue(sections[0][1].startswith("# Refund Policy"))

    def test_preamble_has_empty_path(self):
        text = "Intro line before any heading.\n# Title\nBody."
        sections = parse_sections(text)
        self.assertEqual(sections[0][0], [])
        self.assertIn("Intro line", sections[0][1])
        self.assertEqual(sections[1][0], ["Title"])

    def test_no_headings_returns_single_pathless_section(self):
        text = "Just some plain text.\nNo headings here."
        sections = parse_sections(text)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0][0], [])

    def test_deeper_then_shallower_pops_stack(self):
        text = "# A\n## B\n### C\n# D\nbody"
        paths = [p for p, _ in parse_sections(text)]
        self.assertEqual(paths, [["A"], ["A", "B"], ["A", "B", "C"], ["D"]])


class DocumentChunkerTests(unittest.TestCase):
    def test_each_section_becomes_a_chunk_with_heading_path(self):
        text = "# Refund Policy\nYou may get a refund.\n## Timing\nWithin 30 days."
        chunks = DocumentChunker(chunk_size=1000).chunk(text)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].metadata["heading_path"], ["Refund Policy"])
        self.assertEqual(chunks[1].metadata["heading_path"], ["Refund Policy", "Timing"])

    def test_contiguous_ordinals(self):
        text = "# A\nbody a\n# B\nbody b\n# C\nbody c"
        chunks = DocumentChunker(chunk_size=1000).chunk(text)
        self.assertEqual([c.ordinal for c in chunks], list(range(len(chunks))))

    def test_oversized_section_subsplit_keeps_heading_path(self):
        big_body = " ".join(f"word{i}" for i in range(60))  # long section body
        text = f"# Big Section\n{big_body}"
        chunks = DocumentChunker(chunk_size=50).chunk(text)
        self.assertGreater(len(chunks), 1)  # section was split
        for c in chunks:
            self.assertEqual(c.metadata["heading_path"], ["Big Section"])
            self.assertLessEqual(len(c.text), 50)

    def test_no_headings_falls_back(self):
        text = "Plain text with no headings at all. Another sentence here."
        chunks = DocumentChunker(chunk_size=1000).chunk(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].metadata["heading_path"], [])
        self.assertEqual(chunks[0].metadata.get("fallback"), "recursive")

    def test_empty_returns_empty(self):
        self.assertEqual(DocumentChunker().chunk("   \n "), [])


if __name__ == "__main__":
    unittest.main()
