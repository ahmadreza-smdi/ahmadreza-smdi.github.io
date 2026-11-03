"""Gallery receipt guards exercised against isolated real Git state."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from check_new_carousel_titles import check


class GalleryTitles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = dict(os.environ, GIT_AUTHOR_NAME='Fixture', GIT_COMMITTER_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid', GIT_COMMITTER_EMAIL='fixture@example.invalid')
        self.git('init', '-q')
        self.git('config', 'commit.gpgsign', 'false')
        (self.root / 'README').write_text('Fixture')
        self.git('add', 'README'); self.git('commit', '-qm', 'Base')
        self.relative = 'carousels/test-gallery.html'
        self.page = self.root / self.relative
        self.page.parent.mkdir()
        self.page.write_text(self.html('A' * 65))
        self.receipt = self.root / 'Gallery-Prepared.json'
        self.data = {'status': 'prepared-locally-not-published', 'kind': 'carousel_gallery_batch', 'baseHead': self.git('rev-parse', 'HEAD').strip(), 'committed': False, 'pushed': False, 'liveVerified': False, 'galleryHashes': {}}
        self.save()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, env=self.env, text=True, stderr=subprocess.DEVNULL)

    def html(self, title, kind='CollectionPage'):
        url = 'https://a-samadi.com/' + self.relative
        return '<html><head><title>' + title + '</title><link rel="canonical" href="' + url + '"><script type="application/ld+json">' + json.dumps({'@type': kind, '@id': url + '#gallery', 'url': url}) + '</script></head><body>Fixture</body></html>'

    def save(self):
        self.data['galleryHashes'] = {self.relative: hashlib.sha256(self.page.read_bytes()).hexdigest()}
        self.receipt.write_text(json.dumps(self.data))

    def test_valid_bound_gallery_is_read_only(self):
        before = (self.page.read_bytes(), self.receipt.read_bytes(), self.git('status', '--porcelain'))
        self.assertEqual(check(self.root, self.receipt)[self.relative], 65)
        self.assertEqual(before, (self.page.read_bytes(), self.receipt.read_bytes(), self.git('status', '--porcelain')))

    def test_changed_bytes_rejected(self):
        self.page.write_text(self.html('Changed'))
        with self.assertRaisesRegex(ValueError, 'bytes changed'): check(self.root, self.receipt)

    def test_stale_base_rejected(self):
        self.data['baseHead'] = '0' * 40; self.save()
        with self.assertRaisesRegex(ValueError, 'Stale'): check(self.root, self.receipt)

    def test_article_cannot_borrow_gallery_receipt(self):
        self.page.write_text(self.html('Article', kind='Article')); self.save()
        with self.assertRaisesRegex(ValueError, 'CollectionPage'): check(self.root, self.receipt)

    def test_unbound_new_page_rejected(self):
        (self.root / 'other.html').write_text(self.html('Other'))
        with self.assertRaisesRegex(ValueError, 'all and only'): check(self.root, self.receipt)

    def test_overlong_title_rejected(self):
        self.page.write_text(self.html('A' * 66)); self.save()
        with self.assertRaisesRegex(ValueError, 'exceeds 65'): check(self.root, self.receipt)

    def test_published_and_historical_receipts_rejected(self):
        self.data['pushed'] = True; self.save()
        with self.assertRaisesRegex(ValueError, 'unpublished'): check(self.root, self.receipt)
        self.data['pushed'] = False; self.save()
        self.git('add', self.relative); self.git('commit', '-qm', 'Existing gallery')
        self.data['baseHead'] = self.git('rev-parse', 'HEAD').strip(); self.save()
        with self.assertRaisesRegex(ValueError, 'all and only'): check(self.root, self.receipt)

    def test_symlink_page_rejected(self):
        real = self.root / 'real-file'; real.write_bytes(self.page.read_bytes()); self.page.unlink(); self.page.symlink_to(real)
        with self.assertRaises(OSError): check(self.root, self.receipt)


if __name__ == '__main__':
    unittest.main()
