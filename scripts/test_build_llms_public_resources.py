import unittest
from build_llms import public_resources


class PublicResources(unittest.TestCase):
    def test_visible_owner_link_and_scope_preserved(self):
        text = '<div class="public-tools-data"><h3>Tools</h3><ul><li><a href="https://github.com/ahmadreza-smdi/tool/releases/tag/v1">A &amp; B</a> — Fictional examples; not customer results.</li></ul></div>'
        self.assertEqual(public_resources(text), [('A & B', 'https://github.com/ahmadreza-smdi/tool/releases/tag/v1', 'Fictional examples; not customer results.')])

    def test_unrelated_and_foreign_links_excluded(self):
        self.assertEqual(public_resources('<a href="https://github.com/ahmadreza-smdi/tool">Outside block</a><div class="public-tools-data"><ul><li><a href="https://github.com/other/tool">Foreign</a> — Text.</li></ul></div>'), [])

    def test_absent_block_does_not_invent_projects(self):
        self.assertEqual(public_resources('<p>Biography</p>'), [])

    def test_duplicate_resource_rejected(self):
        item = '<li><a href="https://github.com/ahmadreza-smdi/tool">Tool</a> — Scope.</li>'
        with self.assertRaises(ValueError):
            public_resources('<div class="public-tools-data"><ul>' + item * 2 + '</ul></div>')

    def test_incomplete_block_rejected(self):
        with self.assertRaises(ValueError):
            public_resources('<div class="public-tools-data"><ul><li>Incomplete')


if __name__ == '__main__':
    unittest.main()
