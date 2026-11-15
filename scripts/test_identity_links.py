"""Negative controls for identity assertions; no network or account changes."""
import json
from pathlib import Path
import unittest
from identity_links import add_identity_rel, verified_profiles
from check_identity_links import check_html, name_issues, scoped_strings

class IdentityLinks(unittest.TestCase):
    def test_failing_fixtures(self):
        records=json.loads((Path(__file__).with_name('fixtures')/'identity-negative.json').read_text())
        profiles=verified_profiles()
        for row in records:
            with self.subTest(rule=row['rule']):
                self.assertTrue(any(row['rule'] in issue for issue in check_html(row['html'],'index.html',profiles)))

    def test_rel_preserves_existing_tokens_and_unrelated_urls(self):
        before='<a href="https://github.com/ahmadreza-smdi" rel="nofollow noopener">GitHub</a><a href="https://github.com/ahmadreza-smdi/project">Project</a><a href="https://github.com.evil.test/ahmadreza-smdi">Other</a>'
        after=add_identity_rel(before)
        self.assertEqual(after,before.replace('rel="nofollow noopener"','rel="nofollow noopener me"'))
        self.assertEqual(add_identity_rel(after),after)
        self.assertEqual(check_html(after,'index.html',verified_profiles()),[])

    def test_language_scope(self):
        self.assertEqual(name_issues('احمدرضا صمدی','fa'),[])
        self.assertEqual(name_issues('أحمدرضا صمدي','ar'),[])
        self.assertTrue(name_issues('احمدرضا صمدی','en'))
        self.assertEqual(list(scoped_strings({'locales':[{'language':'fa','name':'احمدرضا صمدی'}]})),[('fa','fa'),('احمدرضا صمدی','fa')])

if __name__=='__main__':unittest.main()
