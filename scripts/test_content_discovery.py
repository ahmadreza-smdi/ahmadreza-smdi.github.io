"""Check source fidelity and coverage across RSS, Ask and the curated catalogue."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

import build_feed as feed
import build_ask_index as ask
import build_llms as llms


class DiscoveryTests(unittest.TestCase):
    def test_rss_preserves_article_content_dates_and_includes_carousels(self):
        xml, count = feed.build_feed()
        items = ET.fromstring(xml).findall('./channel/item')
        by_url = {item.findtext('link'): item for item in items}
        self.assertEqual(len(by_url), count)
        for directory, kind, title in [('writing', 'Article', 'headline'), ('carousels', 'CollectionPage', 'name')]:
            for path in (feed.ROOT / directory).glob('*.html'):
                if path.name == 'index.html':
                    continue
                url = feed.BASE + directory + '/' + path.name
                record = feed.PageMetadata(path).record(kind, url, require_feed=kind == 'Article')
                item = by_url[url]
                self.assertEqual(item.findtext('title'), record[title])
                self.assertEqual(item.findtext('description'), record['description'])
                self.assertEqual(item.findtext('pubDate'), feed.format_datetime(feed.publication_time(record['datePublished']), usegmt=True))
                self.assertEqual(item.findtext('guid'), url)

    def test_rss_related_links_are_existing_films_with_matching_media(self):
        xml, _ = feed.build_feed()
        linked = set()
        for item in ET.fromstring(xml).findall('./channel/item'):
            source = feed.ROOT / item.findtext('link').removeprefix(feed.BASE)
            media = {r['contentUrl'] for r in feed.PageMetadata(source).records
                     if r.get('@type') == 'VideoObject'}
            for related in item.findall('{%s}link' % feed.ATOM):
                self.assertEqual(related.get('rel'), 'related')
                url = related.get('href')
                self.assertTrue(url.startswith(feed.BASE + 'watch/'))
                target = feed.ROOT / url.removeprefix(feed.BASE)
                self.assertTrue(target.is_file())
                video = [r for r in feed.PageMetadata(target).records if r.get('@type') == 'VideoObject'][0]
                self.assertIn(video['contentUrl'], media)
                linked.add(url)
        self.assertIn(feed.BASE + 'watch/business-ai-evaluation-cases.html', linked)

    def test_ask_resource_directory_preserves_homepage_contract_and_sources(self):
        exporter = ask.Exporter(ask.Path(feed.ROOT))
        data = exporter.build()
        self.assertEqual(data['locales'], [exporter.locale(language) for language in ask.LANGUAGES])
        expected = {url for url in exporter.public_pages
                    if url.startswith(tuple(feed.BASE + p for p in ('writing/', 'watch/', 'carousels/')))
                    and url.endswith('.html') and not url.endswith('/index.html')}
        self.assertEqual({r['url'] for r in data['published_resources']}, expected)
        for resource in data['published_resources']:
            metadata = feed.PageMetadata(feed.ROOT / resource['url'].removeprefix(feed.BASE))
            record = [r for r in metadata.records if r.get('@type') == resource['type']][0]
            self.assertEqual(resource['description'], record['description'])
            self.assertEqual(resource['date_published'], record.get('datePublished', record.get('uploadDate')))
        exporter.ensure_unchanged()

    def test_curated_recent_companions_use_publication_date_not_input_order(self):
        def page(day, kind='Article'):
            record = {'@type': kind, 'datePublished': f'2026-10-{day:02d}T21:00:00+03:30'}
            records = [record] + ([{'@type': 'VideoObject'}] if kind == 'Article' else [])
            return '<script type="application/ld+json">' + json.dumps({'@graph': records}) + '</script>'
        pages = {feed.BASE + 'writing/old.html': page(1),
                 feed.BASE + 'carousels/new.html': page(3, 'CollectionPage'),
                 feed.BASE + 'writing/middle.html': page(2)}
        self.assertEqual(llms.recent_companions(pages, 2), {feed.BASE + 'carousels/new.html', feed.BASE + 'writing/middle.html'})
        self.assertEqual(llms.recent_companions(dict(reversed(list(pages.items()))), 2), llms.recent_companions(pages, 2))

    def test_unreviewed_metadata_and_naive_publication_times_fail(self):
        text = '<html lang="en"><link rel="canonical" href="https://wrong.test/"><script type="application/ld+json">' + json.dumps({'@type': 'CollectionPage'}) + '</script>'
        with self.assertRaises(ValueError):
            feed.PageMetadata.from_text(text).record('CollectionPage', feed.BASE + 'carousels/example.html', require_feed=False)
        with self.assertRaises(ValueError):
            feed.publication_time('2026-11-03T14:00:00')


if __name__ == '__main__':
    unittest.main()
