"""Regression coverage for article discovery and author-only transformations."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_author_boxes as builder


class AuthorBoxesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(builder, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def page(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def article(self, lang='en'):
        return ('<!doctype html><html lang="' + lang + '"><head>'
                '<link rel="canonical" href="https://a-samadi.com/writing/example.html">'
                '<script type="application/ld+json">'
                '{"@type":"Article","@id":"https://a-samadi.com/writing/example.html#article","datePublished":"2026-10-01T12:00:00+03:30"}'
                '</script></head><body><article><h1>Unchanged title</h1>'
                '<p>Unchanged evidence.</p></article>'
                '<footer class="editorial-footer">Unchanged footer</footer></body></html>')

    def test_existing_non_article_tool_is_updated_without_reclassifying_it(self):
        path = self.page('tools/embed/rental-cash-flow.html')
        original = '<html lang="en"><head></head><body>' + builder.author_box('en') + '</body></html>'
        updated = builder.enrich_author(path, original)
        self.assertIn('Property Decision Data', updated)
        self.assertNotIn('application/ld+json', updated)
        self.assertIn('target="_blank" rel="author noopener"', updated)
        self.assertEqual(builder.enrich_author(path, updated), updated)

    def test_article_body_and_publication_date_are_untouched(self):
        path = self.page('writing/why-usb-c-cables-differ.html')
        original = self.article()
        updated = builder.enrich_author(path, original)
        stripped = builder.BOX.sub('', updated).replace(builder.STYLESHEET, '').replace('\n', '')
        self.assertEqual(stripped, original)
        self.assertIn('Tech, explained', updated)

    def test_locale_uses_matching_bio_and_same_series(self):
        for lang in ('en', 'fa', 'ar'):
            prefix = '' if lang == 'en' else lang + '/'
            path = self.page(prefix + 'writing/start-with-the-decision.html')
            updated = builder.enrich_author(path, self.article(lang))
            self.assertIn(builder.COPY[lang]['summary'], updated)
            self.assertIn('Start with the Decision', updated)
            self.assertIn(builder.SERIES_PREFIX[lang], updated)

    def test_data_article_classification(self):
        path = self.page('ar/writing/property-data-enrichment.html')
        self.assertEqual(builder.series_for(path), 'Property Decision Data')

    def test_non_article_without_box_is_unchanged(self):
        text = '<html lang="en"><head></head><body>Not an article</body></html>'
        self.assertEqual(builder.enrich_author(self.page('about.html'), text), text)

    def test_duplicate_boxes_fail_before_replacing(self):
        text = self.article() + builder.author_box('en') * 2
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            builder.enrich_author(self.page('writing/example.html'), text)

    def test_recursive_discovery_covers_tools_and_new_article_directories(self):
        paths = [self.page('writing/example.html'), self.page('studies/example.html'),
                 self.page('tools/embed/example.html')]
        for path in paths[:2]:
            path.write_text(self.article())
        paths[2].write_text('<html lang="en"><head></head><body>' + builder.author_box('en') + '</body></html>')
        with patch('sys.argv', ['build_author_boxes.py']):
            builder.main()
        for path in paths:
            self.assertIn('article-author__series', path.read_text())
        with patch('sys.argv', ['build_author_boxes.py', '--check']):
            builder.main()


if __name__ == '__main__':
    unittest.main()
