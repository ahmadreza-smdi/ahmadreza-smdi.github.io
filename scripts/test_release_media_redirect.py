from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock
from check_site_live import compare
from check_media import film_issues, image_issues
from redirect_stubs import inspect
from seo_document import Document, SITE


class ReleaseMarkupTest(unittest.TestCase):
    def setUp(self):
        self.space = TemporaryDirectory()
        self.addCleanup(self.space.cleanup)
        self.root = Path(self.space.name).resolve()

    def test_visible_illustration_requires_exact_image_dimensions(self):
        url = SITE + "assets/writing/topic/diagram.svg"
        doc = Document(f'<img src="{url}" alt="A chart">')
        node = {"@type":"ImageObject", "contentUrl":url, "width":1200, "height":770}
        dimensions = lambda source: (1200, 770)
        self.assertEqual(image_issues(doc, [node], SITE, dimensions), [])
        self.assertTrue(image_issues(doc, [], SITE, dimensions))
        self.assertTrue(image_issues(doc, [dict(node, width=900)], SITE, dimensions))

    def test_each_required_video_field(self):
        for name in ("thumbnail.png", "video.mp4"):
            (self.root / name).write_bytes(b"fixture")
        film = dict(name="Example", description="Released fixture", thumbnailUrl=SITE + "thumbnail.png",
                    duration="PT2.5S", uploadDate="2026-01-02T12:30:00+03:30", contentUrl=SITE + "video.mp4")
        self.assertEqual(film_issues(self.root, film), [])
        for key in film:
            with self.subTest(key=key):
                broken = dict(film)
                del broken[key]
                self.assertTrue(film_issues(self.root, broken))
        for key, value in (("uploadDate","2026-01-02T09:00:00Z"), ("duration","PT0S"),
                           ("thumbnailUrl", SITE+"missing.png"), ("contentUrl",SITE+"missing.mp4")):
            with self.subTest(key=key, value=value):
                self.assertTrue(film_issues(self.root, dict(film, **{key:value})))

    def test_valid_and_invalid_redirects(self):
        (self.root / "fa").mkdir()
        url = SITE + "next.html"
        target = f'<html lang="en"><link rel="canonical" href="{url}"><body>Topic</body></html>'
        (self.root / "next.html").write_text(target)
        template = ('<html lang="en" class="redirect-stub"><head><meta http-equiv="refresh" content="0; url=DEST">'
                    '<link rel="canonical" href="DEST"></head><body><a href="DEST">Read the same topic</a></body></html>')
        def test(src, path="old.html"):
            return inspect(self.root, path, Document(src))
        doc = template.replace("DEST", url)
        self.assertEqual(test(doc), [])
        (self.root / "old.html").write_text(doc)
        reader = Mock()
        reader.get.side_effect = [(200, {}, doc.encode()), (404, {}, b"not found")]
        self.assertFalse(compare(self.root, "old.html", reader)["pass_check"])
        reader.get.side_effect = [(200, {}, doc.encode()), (200, {}, target.encode())]
        self.assertTrue(compare(self.root, "old.html", reader)["pass_check"])
        for destination in (SITE + "old.html", SITE + "404-missing.html", "https://example.com/page"):
            self.assertTrue(test(template.replace("DEST", destination)))
        self.assertTrue(test(doc, "fa/old.html"))
        self.assertTrue(test(doc.replace("</head>", '<meta name="robots" content="noindex"></head>')))
        self.assertTrue(test(doc.replace('0; url=', '5; url=')))
        (self.root / "next.html").write_text(target.replace("<body>", '<meta http-equiv="refresh" content="0; url=/old.html"><body>'))
        self.assertTrue(test(doc))


if __name__ == "__main__":
    unittest.main()
