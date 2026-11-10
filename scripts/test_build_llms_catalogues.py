"""The curated map and complete catalogue must remain truthful and independently checked."""
import contextlib
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import build_llms as catalog


class Catalogues(unittest.TestCase):
    def test_complete_catalogue_covers_each_english_canonical_once(self):
        outputs = catalog.build()
        for url, _ in catalog.entries():
            if catalog.section(url):
                self.assertEqual(outputs['llms-full.txt'].count('](' + url + ')'), 1, url)

    def test_curated_resources_and_film_companions(self):
        outputs = catalog.build()
        primary = outputs['llms.txt']
        self.assertEqual(len(catalog.CORE_PATHS), len(set(catalog.CORE_PATHS)))
        self.assertTrue(25 <= len(catalog.CORE_PATHS) <= 30)
        for path in catalog.CORE_PATHS:
            self.assertEqual(primary.count('](' + catalog.BASE + path + ')'), 1, path)
        self.assertNotIn('## Films', primary)
        self.assertIn('(article + [film]', primary)
        self.assertIn('## Films', outputs['llms-full.txt'])
        self.assertIn('](https://a-samadi.com/llms-full.txt)', primary)

    def test_source_qualifications_are_not_silently_truncated(self):
        for value in ('Only nine short words cannot describe this safely yet', 'word ' * 31):
            with self.assertRaises(ValueError):
                catalog.description(value, 'https://example.test/')
        value = 'This fictional example explains a budget without claiming any measured business result.'
        self.assertEqual(catalog.description(value, 'https://example.test/'), value)

    def test_reviewed_long_sources_keep_complete_fictional_sentences(self):
        for source, sentence in catalog.REVIEWED_DESCRIPTION_SENTENCES.items():
            self.assertGreater(len(source.split()), 30)
            self.assertTrue(source.startswith(sentence))
            self.assertTrue(sentence.endswith('.'))
            self.assertIn('fictional', sentence)
            self.assertEqual(catalog.description(source, 'https://example.test/'), sentence)
            with self.assertRaises(ValueError):
                catalog.description(source + ' Changed source.', 'https://example.test/')

    def test_correct_groups_and_unchanged_identity(self):
        self.assertEqual(catalog.section(catalog.BASE + 'studies/rent-burden/'), 'Studies')
        self.assertEqual(catalog.section(catalog.BASE + 'carousels/example.html'), 'Explainers')
        for output in catalog.build().values():
            self.assertTrue(output.startswith('# Ahmadreza Samadi\n\n> ' + catalog.SUMMARY))
            self.assertNotIn('## Four main topics', output)
            self.assertNotIn('not stated', output)
            self.assertNotIn('threads.', output.lower())
        self.assertEqual([p[0] for p in catalog.PROFILES[:3]], ['GitHub', 'YouTube', 'DEV'])

    def test_every_link_entry_has_ten_to_thirty_description_words(self):
        for output in catalog.build().values():
            for line in output.splitlines():
                if line.startswith('- ['):
                    copy = line.split('): ', 1)[1]
                    self.assertTrue(10 <= len(copy.split()) <= 30, line)

    def test_check_detects_stale_full_output_when_curated_is_current(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'llms.txt').write_text('curated')
            (root / 'llms-full.txt').write_text('stale')
            with patch.object(catalog, 'ROOT', root), patch.object(catalog, 'build', return_value={
                    'llms.txt': 'curated', 'llms-full.txt': 'complete'}), patch('sys.argv', ['build_llms.py', '--check']):
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
                    catalog.main()
                self.assertEqual(result.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
