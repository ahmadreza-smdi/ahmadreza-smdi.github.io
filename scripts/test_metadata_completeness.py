"""Completeness regressions: preserve dates, canonical URLs and noindex scope."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
import enrich_metadata as metadata


class MetadataCompleteness(TestCase):
    def test_carousel_title_attribution_respects_limit_and_is_idempotent(self):
        path = metadata.ROOT / 'carousels/example.html'
        for count in (46, 47):
            title = 'A' * count
            source = '<html lang="en"><head><title>' + title + '</title><meta property="og:title" content="Example"></head></html>'
            result, _ = metadata.enrich(path, source)
            expected = title + ' | Ahmadreza Samadi' if count == 46 else title
            self.assertIn('<title>' + expected + '</title>', result)
            self.assertEqual(metadata.enrich(path, result)[0], result)

    def test_recorded_update_does_not_expand_bare_id_references(self):
        path = metadata.ROOT / 'about.html'
        page_id = metadata.BASE + 'about.html#profile'
        source = '<html lang="en"><head><link rel="canonical" href="https://a-samadi.com/about.html"><script type="application/ld+json">' + json.dumps({'@graph': [
            {'@type': 'ProfilePage', '@id': page_id, 'dateModified': '2026-10-01'},
            {'@type': 'Person', '@id': metadata.BASE + '#person', 'mainEntityOfPage': {'@id': page_id}},
        ]}) + '</script></head><h1>About</h1>'
        with patch.object(metadata, 'CONTENT_UPDATES', {'about.html': {'dateModified': '2026-10-28T22:00:00+03:30'}}):
            result, _ = metadata.complete_schema(path, source)
        graph = json.loads(metadata.LD.search(result)[2])['@graph']
        self.assertEqual(graph[0]['dateModified'], '2026-10-28T22:00:00+03:30')
        self.assertEqual(graph[1]['mainEntityOfPage'], {'@id': page_id})

    def test_unreviewed_description_change_fails_closed(self):
        path = metadata.ROOT / 'example.html'
        source = '<html lang="en"><head><meta name="description" content="A newly edited source."></head></html>'
        record = {'previous': 'Previously reviewed source.', 'description': 'A' * 125}
        with patch.object(metadata, 'DESCRIPTION_UPDATES', {'example.html': record}):
            with self.assertRaisesRegex(ValueError, 'description source changed'):
                metadata.enrich(path, source)

    def test_article_additions_preserve_frozen_dates_and_use_existing_parent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'writing').mkdir()
            (root / 'writing/index.html').write_text('<link rel="canonical" href="https://a-samadi.com/writing/">')
            article = {'@type': 'Article', '@id': 'https://a-samadi.com/writing/example.html#article', 'datePublished': '2026-10-01', 'dateModified': '2026-10-02'}
            source = '<html lang="en"><head><link rel="canonical" href="https://a-samadi.com/writing/example.html"><script type="application/ld+json">' + json.dumps({'@graph': [article]}) + '</script></head><h1>Example</h1>'
            with patch.object(metadata, 'ROOT', root):
                result, changes = metadata.complete_schema(root / 'writing/example.html', source)
                graph = json.loads(metadata.LD.search(result)[2])['@graph']
                self.assertEqual(graph[0], dict(article, publisher={'@id': metadata.BASE + '#person'}))
                self.assertEqual([i['item'] for i in graph[1]['itemListElement']], [metadata.BASE, metadata.BASE + 'writing/', metadata.BASE + 'writing/example.html'])
                self.assertEqual(metadata.complete_schema(root / 'writing/example.html', result), (result, []))

    def test_no_fabricated_tools_parent_and_noindex_exclusion(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = '<html lang="en"><head><link rel="canonical" href="https://a-samadi.com/tools/example.html"></head><h1>Tool</h1>'
            with patch.object(metadata, 'ROOT', root):
                result, _ = metadata.complete_schema(root / 'tools/example.html', source)
                trail = json.loads(metadata.LD.search(result)[2])['itemListElement']
                self.assertEqual(len(trail), 2)
                excluded = source.replace('</head>', '<meta name="robots" content="noindex,follow"></head>')
                self.assertEqual(metadata.complete_schema(root / 'tools/embed/example.html', excluded), (excluded, []))


if __name__ == '__main__':
    main()
