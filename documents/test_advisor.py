"""Unit tests for the auto-advisor heuristics (pure functions, no DB/LLM).

    docker compose exec web python -m unittest documents.test_advisor -v
"""

from __future__ import annotations

import unittest

from documents.advisor import profile_text, recommend


class ProfileTests(unittest.TestCase):
    def test_counts_headings_and_sentences(self):
        text = "# Title\nOne sentence here. Two sentence here.\n## Sub\nThree here."
        p = profile_text(text)
        self.assertEqual(p.heading_count, 2)
        self.assertTrue(p.has_structure)
        self.assertGreaterEqual(p.sentence_count, 3)

    def test_arabic_ratio(self):
        p = profile_text("مرحبا بالعالم hello")
        self.assertGreater(p.arabic_ratio, 0.5)

    def test_empty(self):
        p = profile_text("")
        self.assertEqual(p.char_count, 0)
        self.assertEqual(p.arabic_ratio, 0.0)


class RecommendTests(unittest.TestCase):
    def test_structured_doc_recommends_document(self):
        text = "# A\nbody one here.\n## B\nbody two here.\n# C\nbody three here."
        self.assertEqual(recommend(profile_text(text)).strategy, "document")

    def test_short_doc_recommends_sentence(self):
        self.assertEqual(recommend(profile_text("Just one short line.")).strategy, "sentence")

    def test_arabic_heavy_recommends_token(self):
        # long enough to pass the short-doc gate, majority Arabic, no headings
        text = ("هذا نص عربي طويل بما يكفي لتجاوز حد المستند القصير. " * 8)
        rec = recommend(profile_text(text))
        self.assertEqual(rec.strategy, "token")

    def test_long_plain_prose_recommends_recursive(self):
        text = "This is ordinary english prose without any headings. " * 15
        self.assertEqual(recommend(profile_text(text)).strategy, "recursive")

    def test_reason_is_populated(self):
        rec = recommend(profile_text("# H1\na.\n## H2\nb."))
        self.assertTrue(rec.reason)
        self.assertIn("heading", rec.reason.lower())


if __name__ == "__main__":
    unittest.main()
