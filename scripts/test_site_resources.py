"""Check discovery, missing resource failures and live comparisons without sending HTTP requests."""

from pathlib import Path
import tempfile
import subprocess
from hashlib import sha256
import unittest
from check_site_live import Reader, compare, excluded_files
from site_resources import inventory


class Response:
    def __init__(self, status, data=b"", headers=None):
        self.status, self.data, self.headers = status, data, headers or {}

    def get(self, url, partial=False):
        return self.status, self.headers, self.data

    def checksum(self, url):
        return (
            self.status,
            self.headers,
            (len(self.data), sha256(self.data).hexdigest()),
        )


class Resources(unittest.TestCase):
    def test_reachable_chain_and_broken_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, text in {
                "index.html": '<html><script type="module" src="/main.mjs"></script><link rel="stylesheet" href="/main.css"></html>',
                "main.css": 'a{background:url("/pic.png")}',
                "main.mjs": "import './app.js';",
                "app.js": "fetch('./data.json')",
                "data.json": "[]",
                "pic.png": "sample",
                "_config.yml": "exclude:\n  - private/example.py\n",
            }.items():
                (root / name).write_text(text)
            pages, reachable, refs, missing = inventory(root)
            self.assertEqual(pages, {"index.html"})
            self.assertEqual(missing, set())
            self.assertEqual(
                reachable,
                pages | {"main.css", "main.mjs", "app.js", "data.json", "pic.png"},
            )
            self.assertEqual(refs["data.json"], {"app.js"})
            self.assertFalse(set(excluded_files(root)) & reachable)
            (root / "data.json").unlink()
            self.assertIn(("app.js", "data.json"), inventory(root)[3])

    def test_published_csv_uses_git_line_endings_but_never_masks_new_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                subprocess.run(
                    [
                        "git",
                        "-c",
                        "user.name=Fixture",
                        "-c",
                        "user.email=test@example.invalid",
                        "-c",
                        "core.hooksPath=/dev/null",
                        "-c",
                        "core.autocrlf=false",
                        *args,
                    ],
                    cwd=root,
                    check=True,
                    capture_output=True,
                )

            git("init", "-q")
            path = root / "data.csv"
            published = b"label,value\nexample,12\n"
            path.write_bytes(published)
            git("add", "--", path.name)
            git("commit", "-qm", "Test source")
            path.write_bytes(published.replace(b"\n", b"\r\n"))
            result = compare(root, path.name, Response(200, published))
            self.assertTrue(result["pass_check"])
            self.assertTrue(result["reference"].startswith("committed CSV"))
            path.write_bytes(path.read_bytes().replace(b"12", b"13"))
            self.assertFalse(
                compare(root, path.name, Response(200, published))["pass_check"]
            )

    def test_wrong_status_wrong_content_and_full_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_bytes(b"before<!--email_off-->after")
            for response, expected in [
                (Response(404), False),
                (Response(200, b"edited"), False),
                (Response(200, b"beforeafter"), True),
            ]:
                self.assertEqual(
                    compare(root, "index.html", response)["pass_check"], expected
                )
            self.assertFalse(
                compare(root, "index.html", Response(200), True)["pass_check"]
            )
            self.assertTrue(
                compare(root, "index.html", Response(404), True)["pass_check"]
            )
            (root / "large.mp4").write_bytes(b"0" * 700000)
            for data, expected in [
                (b"0" * 700000, True),
                (b"0" * 600000, False),
                (b"0" * 699999 + b"9", False),
            ]:
                resp = Response(200, data)
                self.assertEqual(
                    compare(root, "large.mp4", resp)["pass_check"], expected
                )
            (root / "_config.yml").write_text("exclude:\n  - ../outside.py\n")
            with self.assertRaises(ValueError):
                excluded_files(root)
            with self.assertRaises(ValueError):
                Reader().get("https://example.org/test")


if __name__ == "__main__":
    unittest.main()
