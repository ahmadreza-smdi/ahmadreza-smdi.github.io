"""Regression tests for crawlable internal links and fragment targets."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

from check_internal_links import audit


class InternalLinkTests(TestCase):
    def test_orphan_check_needs_a_distinct_indexable_source(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://a-samadi.com/watch.html</loc></url></urlset>')
            (root / 'watch.html').write_text('<a href="/watch.html">Self</a>')
            (root / 'embed.html').write_text('<meta name="robots" content="noindex"><a href="/watch.html">Film</a>')
            self.assertEqual(len(audit(root, check_orphans=True)[2]), 1)
            (root / 'article.html').write_text('<a href="/watch.html#player">Watch</a>')
            (root / 'watch.html').write_text('<video id="player"></video>')
            self.assertEqual(audit(root, check_orphans=True)[2], [])

    def test_resolves_local_paths_and_fragments(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fa").mkdir()
            (root / "index.html").write_text(
                '<a href="/fa/#intro">Persian</a><a href="mailto:test@example.com">Email</a>',
                encoding="utf-8",
            )
            (root / "fa/index.html").write_text('<section id="intro"></section>', encoding="utf-8")
            self.assertEqual(audit(root), (2, 1, []))

    def test_reports_missing_file_and_fragment(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text(
                '<a href="/missing.html">Missing</a><a href="#absent">Section</a>',
                encoding="utf-8",
            )
            count, checked, problems = audit(root)
            self.assertEqual((count, checked), (1, 2))
            self.assertEqual(len(problems), 2)
            self.assertIn("missing local file", problems[0])
            self.assertIn("missing fragment", problems[1])


if __name__ == "__main__":
    main()
