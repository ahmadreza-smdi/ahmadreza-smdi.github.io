"""Negative controls for the positioning, locale, link and initial-weight checks."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from check_brand import document_findings, inspect_page
from check_page_quality import audit, graph_errors, persian_typography
from seo_document import Document, SITE


class PageQuality(unittest.TestCase):
    def test_identity_lead_including_a_property_study(self):
        def check(node, path="index.html"):
            raw = '<html lang="en"><head><script type="application/ld+json">' + json.dumps(node) + '</script></head></html>'
            return {f.rule for f in inspect_page(path, raw)[-1]}
        for field, value in (("description", "Real estate before AI"), ("knowsAbout", ["Housing", "Business AI"]),
                             ("description", "AI for property decisions")):
            with self.subTest(field=field, value=value):
                node = {"@type": "Person", "@id": SITE + "#person", field: value}
                self.assertIn("BR-IDENTITY-LEAD", check(node, "studies/rent-burden/index.html"))
        # Study scope and organizations legitimately lead with their field.
        for kind in ("Dataset", "Organization"):
            self.assertNotIn("BR-IDENTITY-LEAD", check({"@type": kind, "description": "Real estate valuation study"}))
        self.assertNotIn("BR-IDENTITY-LEAD", check({"@type": "Person", "@id": SITE + "#person",
                                                    "description": "Technology entrepreneur building AI for property decisions"}))
        for name in ("llms.txt", "llms-full.txt"):
            self.assertIn("BR-IDENTITY-LEAD", {f.rule for f in document_findings(name, "> Real estate before AI\n")})

    def test_orphans_depth_and_redirects(self):
        graph = {"index.html": {"1.html"}, "1.html": {"2.html"}, "2.html": {"3.html"},
                 "3.html": {"4.html", "old.html"}, "4.html": set(), "orphan.html": set(), "old.html": set()}
        issues = graph_errors(graph, set(graph) - {"old.html"}, {"old.html"})
        self.assertIn("4.html: deeper than three clicks from index.html", issues)
        self.assertIn("orphan.html: orphan", issues)
        self.assertIn("3.html: links to redirect old.html", issues)
        self.assertFalse(any(e.startswith("3.html: deeper") for e in issues))

    def test_persian_typography_and_quoted_name(self):
        def verify(content):
            return persian_typography(Document('<html lang="fa"><body>' + content + '</body></html>'))
        self.assertTrue(verify("كتاب"))
        self.assertTrue(verify("احمدرضا صمدي"))
        self.assertFalse(verify('کتاب · أحمدرضا صمدي · <q lang="ar">كتاب</q>'))

    def test_asset_budget_dimensions_and_alternate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = '<html lang="en"><head><link rel="canonical" href="' + SITE + '"><link rel="alternate" hreflang="fa" href="' + SITE + '"></head><body><img src="test.png"></body></html>'
            (root / "index.html").write_text(doc)
            (root / "test.png").write_bytes(b"x" * 400)
            _, errors = audit(root, budget=350)
            self.assertTrue(any("self-canonical fa" in e for e in errors))
            self.assertTrue(any("dimensions" in e for e in errors))
            self.assertTrue(any("budget exceeded" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
