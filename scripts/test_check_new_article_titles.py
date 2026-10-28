"""Behavioral CLI tests using isolated real Git repositories; no network."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).absolute().with_name('check_new_article_titles.py')
GIT_ENV = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_AUTHOR_NAME='Ahmadreza Samadi',
               GIT_AUTHOR_EMAIL='ahmadreza.smdi@gmail.com',
               GIT_COMMITTER_NAME='Ahmadreza Samadi',
               GIT_COMMITTER_EMAIL='ahmadreza.smdi@gmail.com')


class DailyTitleCLI(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='new-daily-title-test-')
        self.addCleanup(self.temporary.cleanup)
        # macOS tempfile aliases /var through /private/var. Use the actual
        # fixture directory so the guard can still refuse symlink arguments.
        self.directory = Path(self.temporary.name).resolve()
        self.root = self.directory / 'Website'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'commit.gpgsign', 'false')
        (self.root / 'README.txt').write_text('Isolated title guard test fixture.\n')
        self.git('add', 'README.txt')
        self.git('commit', '-qm', 'Fixture base')
        self.slug = 'test-new-daily-family'
        self.paths = {lang: prefix + 'writing/' + self.slug + '.html'
                      for lang, prefix in (('en', ''), ('fa', 'fa/'), ('ar', 'ar/'))}
        for relative in self.paths.values():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.html(relative, 'Decision &amp; property'), encoding='utf-8')
        self.receipt = self.directory / 'Release-Prepared.json'
        self.receipt_data = {
            'status': 'prepared-locally-not-published', 'slug': self.slug,
            'baseHead': self.git('rev-parse', 'HEAD').strip(),
            'automatic_daily_exception': True, 'committed': False,
            'pushed': False, 'liveVerified': False,
            'ownedHashes': {relative: hashlib.sha256((self.root / relative).read_bytes()).hexdigest()
                            for relative in self.paths.values()},
            'human_fact_check_performed': False, 'native_human_review_performed': False,
        }
        self.save_receipt()

    def git(self, *arguments):
        return subprocess.check_output(['git', *arguments], cwd=self.root, env=GIT_ENV,
                                       stderr=subprocess.DEVNULL, text=True)

    def html(self, relative, title):
        return ('<!doctype html><html><head><meta charset="utf-8"><title>' + title
                + '</title><link rel="canonical" href="https://a-samadi.com/' + relative
                + '"><script type="application/ld+json">'
                + '{"@context":"https://schema.org","@type":"Article",'
                + '"headline":"Synthetic test fixture"}</script></head>'
                + '<body><main><h1>Synthetic test fixture</h1></main></body></html>\n')

    def title(self, lang, title):
        relative = self.paths[lang]
        (self.root / relative).write_text(self.html(relative, title), encoding='utf-8')

    def save_receipt(self):
        self.receipt.write_text(json.dumps(self.receipt_data, ensure_ascii=False), encoding='utf-8')

    def state(self):
        files = {}
        for parent, dirs, names in os.walk(self.directory, followlinks=False):
            for name in dirs + names:
                path = Path(parent) / name
                relative = str(path.relative_to(self.directory))
                if path.is_symlink():
                    files[relative] = ('symlink', os.readlink(path))
                elif path.is_file():
                    files[relative] = ('file', path.read_bytes())
        return (files, self.git('rev-parse', 'HEAD'),
                self.git('status', '--porcelain=v1', '--untracked-files=all'))

    def run_check(self, expected=0, receipt=None, root=None, script=None, default_root=False):
        before = self.state()
        command = [sys.executable, '-B', str(script or SCRIPT), '--release-receipt',
                   str(receipt or self.receipt)]
        if not default_root:
            command += ['--root', str(root or self.root)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, env=GIT_ENV)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(self.state(), before, 'Checker changed input bytes or Git state')
        if expected:
            self.assertIn('FAIL:', result.stderr)
            self.assertNotIn('PASS:', result.stdout)
        else:
            self.assertIn('PASS:', result.stdout)
        return result

    def test_sixty_unicode_characters_are_accepted(self):
        for lang, character in (('en', 'A'), ('fa', 'پ'), ('ar', 'ع')):
            self.title(lang, character * 60)
        result = self.run_check()
        self.assertIn('en 60, fa 60, ar 60', result.stdout)

    def test_entity_decoding_uses_rendered_sixty_character_boundary(self):
        self.title('en', 'A' * 58 + '&amp;Z')
        self.title('fa', '&#1662;' * 60)
        self.title('ar', '&#x639;' * 60)
        result = self.run_check()
        self.assertIn('en 60, fa 60, ar 60', result.stdout)
        self.title('en', 'A' * 59 + '&amp;Z')
        self.assertIn('exceeds 60', self.run_check(1).stderr)

    def test_whitespace_is_collapsed_without_counting_source_entity_bytes(self):
        self.title('en', ' \n\tDecision   &amp;   property  \t')
        self.assertIn('en 19', self.run_check().stdout)

    def test_each_locale_overlong_title_is_refused(self):
        for lang, character in (('en', 'A'), ('fa', 'پ'), ('ar', 'ع')):
            with self.subTest(lang=lang):
                self.title(lang, character * 61)
                result = self.run_check(1)
                self.assertIn(self.paths[lang], result.stderr)
                self.assertIn('exceeds 60', result.stderr)
                self.title(lang, 'Short title')

    def test_combining_characters_count_as_unicode_code_points(self):
        self.title('en', 'e\u0301' * 30 + 'Z')
        self.assertIn('exceeds 60', self.run_check(1).stderr)

    def test_svg_accessibility_titles_do_not_change_head_title_scope_or_length(self):
        for relative in self.paths.values():
            path = self.root / relative
            path.write_text(path.read_text().replace('</main>',
                '<svg role="img"><title>Accessible chart description</title></svg>'
                '<svg><title>' + 'A' * 100 + '</title><svg><title>Nested chart</title>'
                '</svg></svg><svg><title/></svg><svg/></main>'))
        result = self.run_check()
        self.assertIn('en 19, fa 19, ar 19', result.stdout)

    def test_svg_titles_cannot_supply_or_duplicate_a_head_title(self):
        original = self.html(self.paths['en'], 'Short title')
        svg = '<svg><title>Accessible chart</title></svg>'
        for text in (
                original.replace('<title>Short title</title>', '').replace('</main>', svg + '</main>'),
                original.replace('</head>', '<title>Duplicate</title></head>').replace('</main>', svg + '</main>'),
                original.replace('<title>Short title</title>', svg),
                original.replace('</title>', '').replace('</main>', svg + '</main>')):
            with self.subTest(text=text[:90]):
                (self.root / self.paths['en']).write_text(text)
                self.run_check(1)

    def test_only_invisible_format_control_or_whitespace_title_is_refused(self):
        for title in ('\u200b', '&ZeroWidthSpace;', '\u200c\u200d\ufeff',
                      ' \t\u2066\u2069\u0001\u0085 '):
            with self.subTest(title=repr(title)):
                self.title('en', title)
                self.assertIn('rendered text', self.run_check(1).stderr)

    def test_farsi_zwnj_is_retained_and_counted_inside_words(self):
        self.title('fa', 'می\u200cشود')
        self.assertIn('fa 6', self.run_check().stdout)
        self.title('fa', 'می\u200cشود' * 10)
        self.assertIn('fa 60', self.run_check().stdout)
        self.title('fa', 'می\u200cشود' * 10 + '\u200c')
        self.assertIn('exceeds 60', self.run_check(1).stderr)

    def test_post_sync_bytes_do_not_need_to_match_pre_sync_helper_hashes(self):
        for relative in self.paths.values():
            path = self.root / relative
            path.write_text(path.read_text().replace('</main>', '<p>Part of: reviewed hub</p></main>'))
        self.run_check()

    def test_receipt_base_must_be_full_and_current(self):
        original = self.receipt_data['baseHead']
        for base in (original[:8], '0' * 40, 'HEAD', None):
            with self.subTest(base=base):
                self.receipt_data['baseHead'] = base
                self.save_receipt()
                self.assertIn('baseHead', self.run_check(1).stderr)

    def test_head_advance_makes_prior_receipt_stale(self):
        (self.root / 'README.txt').write_text('Actual later fixture commit.\n')
        self.git('add', 'README.txt')
        self.git('commit', '-qm', 'Advance fixture HEAD')
        self.assertIn('baseHead', self.run_check(1).stderr)

    def test_historical_page_is_refused_even_with_rebased_receipt(self):
        self.git('add', self.paths['en'])
        self.git('commit', '-qm', 'One family path already exists')
        self.receipt_data['baseHead'] = self.git('rev-parse', 'HEAD').strip()
        self.save_receipt()
        self.assertIn('historical pages', self.run_check(1).stderr)

    def test_local_automatic_uncommitted_receipt_is_required(self):
        cases = [('status', 'private-preflight-passed'), ('status', 'published'),
                 ('automatic_daily_exception', False), ('automatic_daily_exception', 1),
                 ('committed', True), ('committed', 0), ('pushed', True),
                 ('liveVerified', True)]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                original = self.receipt_data[key]
                self.receipt_data[key] = value
                self.save_receipt()
                self.run_check(1)
                self.receipt_data[key] = original
                self.save_receipt()

    def test_missing_or_malformed_owned_family_declaration_is_refused(self):
        original = dict(self.receipt_data['ownedHashes'])
        for owned in (None, {}, {self.paths['en']: original[self.paths['en']]},
                      {**original, self.paths['fa']: 'bad-digest'},
                      {**original, '../outside.html': 'a' * 64}):
            with self.subTest(owned=owned):
                self.receipt_data['ownedHashes'] = owned
                self.save_receipt()
                self.run_check(1)

    def test_unsafe_slug_cannot_escape_or_name_another_family(self):
        for slug in ('../outside', '/outside', 'Upper-Case', 'one--two', '', 'a.html', None):
            with self.subTest(slug=slug):
                self.receipt_data['slug'] = slug
                self.save_receipt()
                self.run_check(1)

    def test_wrong_receipt_filename_is_refused_before_content_read(self):
        other = self.directory / 'Not-A-Helper-Receipt.json'
        other.write_text('DO_NOT_READ_THIS_SENTINEL', encoding='utf-8')
        result = self.run_check(1, receipt=other)
        self.assertIn('filename', result.stderr)
        self.assertNotIn('SENTINEL', result.stderr)

    def test_symlink_receipt_and_symlink_ancestor_are_refused(self):
        original = self.directory / 'Actual-Receipt.json'
        self.receipt.rename(original)
        self.receipt.symlink_to(original)
        self.run_check(1)
        self.receipt.unlink()
        original.rename(self.receipt)
        linked_parent = self.directory / 'Linked-Receipts'
        linked_parent.symlink_to(self.directory, target_is_directory=True)
        self.run_check(1, receipt=linked_parent / 'Release-Prepared.json')

    def test_symlink_article_and_symlink_locale_directory_are_refused(self):
        path = self.root / self.paths['en']
        outside = self.directory / 'Outside.html'
        path.rename(outside)
        path.symlink_to(outside)
        self.run_check(1)
        path.unlink()
        outside.rename(path)
        locale = self.root / 'fa'
        outside_locale = self.directory / 'Outside-Locale'
        locale.rename(outside_locale)
        locale.symlink_to(outside_locale, target_is_directory=True)
        self.run_check(1)

    def test_parent_traversal_and_symlink_root_are_refused(self):
        linked_root = self.directory / 'Linked-Website'
        linked_root.symlink_to(self.root, target_is_directory=True)
        self.run_check(1, root=linked_root)
        self.run_check(1, receipt=self.root / '..' / 'Release-Prepared.json')

    def test_duplicate_keys_and_invalid_json_are_refused(self):
        for text in ('{"slug":"first","slug":"second"}', '{broken', '[]'):
            with self.subTest(text=text):
                self.receipt.write_text(text)
                self.run_check(1)

    def test_missing_empty_duplicate_or_malformed_title_is_refused(self):
        original = self.html(self.paths['en'], 'Short title')
        cases = [
            original.replace('<title>Short title</title>', ''),
            original.replace('Short title</title>', ' \n\t&nbsp; </title>'),
            original.replace('</title>', '</title><title>Duplicate</title>'),
            original.replace('</title>', ''),
            original.replace('<title>Short title</title>', '<title/>'),
            original.replace('<title>Short title</title>', '</title><title>Short title</title>'),
            original.replace('<title>Short title</title>', '').replace('<body>', '<body><title>Outside</title>'),
            original.replace('</head>', ''),
        ]
        for text in cases:
            with self.subTest(text=text[:90]):
                (self.root / self.paths['en']).write_text(text)
                self.run_check(1)

    def test_literal_markup_in_rcdata_title_is_counted_instead_of_stripped(self):
        # A browser renders tag/comment-looking text inside title literally.
        # Long such text must not become a shorter title by stripping tags.
        self.title('en', '<b>' + 'A' * 57 + '</b>')
        self.assertIn('exceeds 60', self.run_check(1).stderr)
        self.title('en', '<!-- ' + 'A' * 54 + ' -->')
        self.assertIn('exceeds 60', self.run_check(1).stderr)

    def test_current_self_canonical_must_be_unique_and_exact(self):
        original = self.html(self.paths['en'], 'Short title')
        canonical = '<link rel="canonical" href="https://a-samadi.com/' + self.paths['en'] + '">'
        for text in (original.replace(canonical, ''), original.replace(canonical, canonical * 2),
                     original.replace(self.paths['en'], self.paths['fa']),
                     original.replace('rel="canonical"', 'rel="canonical" rel="stylesheet"'),
                     original.replace('https://a-samadi.com/', 'https://other.invalid/')):
            with self.subTest(text=text[:90]):
                (self.root / self.paths['en']).write_text(text)
                self.run_check(1)

    def test_missing_or_non_utf8_current_article_is_refused(self):
        path = self.root / self.paths['fa']
        path.unlink()
        self.run_check(1)
        path.write_bytes(b'\xff\xfe')
        self.run_check(1)

    def test_default_root_works_when_installed_in_repository_scripts(self):
        installed = self.root / 'scripts' / SCRIPT.name
        installed.parent.mkdir()
        shutil.copyfile(SCRIPT, installed)
        self.run_check(script=installed, default_root=True)

    def maintenance_check(self, expected=0):
        before = self.state()
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(self.root)],
                                capture_output=True, text=True, timeout=15, env=GIT_ENV)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(self.state(), before, 'Maintenance check must be read-only')
        return result

    def commit_existing_pages(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'Existing page fixtures')

    def test_maintenance_refuses_new_untracked_or_staged_pages(self):
        self.assertIn('require --release-receipt', self.maintenance_check(1).stderr)
        self.git('add', '.')
        self.assertIn('require --release-receipt', self.maintenance_check(1).stderr)

    def test_maintenance_accepts_65_decoded_characters_but_refuses_66(self):
        self.commit_existing_pages()
        self.title('en', 'A' * 64 + '&amp;')
        self.assertIn('1 changed indexable pages', self.maintenance_check().stdout)
        self.title('en', 'A' * 65 + '&amp;')
        self.assertIn('exceeds 65', self.maintenance_check(1).stderr)

    def test_maintenance_preserves_self_canonical_and_head_structure_checks(self):
        self.commit_existing_pages()
        path = self.root / self.paths['en']
        original = path.read_text()
        path.write_text(original.replace('https://a-samadi.com/', 'https://example.com/'))
        self.assertIn('self-canonical', self.maintenance_check(1).stderr)
        path.write_text(original.replace('</head>', '<title>Duplicate</title></head>'))
        self.maintenance_check(1)

    def test_maintenance_noindex_embed_does_not_need_parent_self_canonical(self):
        path = self.root / self.paths['en']
        source = self.html('tools/parent.html', 'A' * 70).replace(
            '</head>', '<meta name="robots" content="noindex,follow"></head>')
        path.write_text(source)
        self.commit_existing_pages()
        path.write_text(source.replace('</title>', ' (embed)</title>'))
        self.assertIn('0 changed indexable pages', self.maintenance_check().stdout)

    def test_maintenance_rejects_symlink_replacement(self):
        self.commit_existing_pages()
        path = self.root / self.paths['en']
        target = self.directory / 'external.html'
        target.write_bytes(path.read_bytes())
        path.unlink(); path.symlink_to(target)
        self.maintenance_check(1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
