"""Regression guards for stateful styles and stale generated film pages."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import build_film_css as css


DOC = '<!doctype html><html><head><link rel="stylesheet" href="/css/site.css?v=test"></head><body class="editorial-body"><main class="editorial"><h1>Film</h1><a href="/">Home</a><details class="watch-transcript"><summary>Transcript</summary><p>Text</p></details><video controls preload="metadata" poster="/cover.jpg"><source src="/film.mp4"></video></main></body></html>'
SOURCE = '.editorial h1{color:red}.unused{color:blue}.watch-transcript[open]>summary::after{content:"−"}a:hover,a:focus-visible{outline:2px solid red}@media print{.editorial{display:block}}'


class FilmCssTests(unittest.TestCase):
    def test_open_hover_focus_and_print_survive(self):
        result, _ = css.extract(SOURCE, DOC, 'css/site.css')
        self.assertIn('[open]>summary::after', result)
        self.assertIn('a:hover,a:focus-visible', result)
        self.assertIn('@media print', result)
        self.assertNotIn('.unused', result)

    def test_unknown_selectors_are_kept(self):
        result, info = css.extract('.editorial:future-state{color:red}', DOC, 'css/site.css')
        self.assertIn(':future-state', result)
        self.assertTrue(info['conservative_selectors'])

    def test_urls_rebased_without_corrupting_data_or_fragments(self):
        source = '.editorial{background:url("../assets/a(b).svg");mask:url(#mask)}@font-face{font-family:X;src:url(../assets/font.woff2)}.editorial h1{background:url("data:image/svg+xml,<svg></svg>")}'
        result, _ = css.extract(source, DOC, 'css/site.css')
        self.assertIn('url("/assets/a(b).svg")', result)
        self.assertIn('url("/assets/font.woff2")', result)
        self.assertIn('url(#mask)', result)
        self.assertIn('data:image/svg+xml,<svg></svg>', result)

    def test_styles_only_round_trip(self):
        result, sheets = css.render(DOC, {'css/site.css': SOURCE.encode()})
        self.assertEqual(css.original_html(result, {'sheets': sheets}), DOC)
        self.assertEqual(result.split('</head>')[1], DOC.split('</head>')[1])

    def test_unapproved_source_and_style_end_tag_fail(self):
        with self.assertRaises(ValueError):
            css.render(DOC.replace('/css/site.css?v=test', 'https://external.example/style.css'), {})
        with self.assertRaises(ValueError):
            css.extract('.editorial{content:"</style>"}', DOC, 'css/site.css')

    def test_check_rejects_changed_page_css_output_and_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in css.ALLOWED:
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text(SOURCE)
            result, sheets = css.render(DOC, {'css/site.css': SOURCE.encode()})
            page = root / 'film.html'; page.write_text(result)
            config = {'version': 1, 'generator_sha256': css.digest(Path(css.__file__).read_bytes()), 'pages': {'film.html': {'original_sha256': css.digest(DOC), 'output_sha256': css.digest(result), 'sheets': sheets}}}
            self.assertEqual(css.check(root, config), 1)
            for changed in [result.replace('<h1>Film', '<h1>Changed film'), result.replace('color:red', 'color:green'), result.replace('film-css:end:', 'film-css:broken:')]:
                page.write_text(changed)
                with self.assertRaises(ValueError): css.check(root, config)
            page.write_text(result)
            (root / 'css/site.css').write_text(SOURCE + '.editorial{padding:1rem}')
            with self.assertRaises(ValueError): css.check(root, config)
            (root / 'css/site.css').write_text(SOURCE)
            bad = copy.deepcopy(config); bad['generator_sha256'] = 'changed'
            with self.assertRaises(ValueError): css.check(root, bad)


if __name__ == '__main__':
    unittest.main()
