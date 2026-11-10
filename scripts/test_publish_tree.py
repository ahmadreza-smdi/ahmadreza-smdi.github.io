"""Offline fixtures for the manual publish allowlist."""
from pathlib import Path
import json
import subprocess
from tempfile import TemporaryDirectory
import unittest
from build_publish_tree import DISCOVERY, build, select


class PublishTreeTest(unittest.TestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name).resolve() / "repository"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        for path in DISCOVERY:
            self.write(path, "")
        self.write("site.webmanifest", '{"icons":[]}')
        self.write("_config.yml", "exclude:\n  - audit.py\n")
        self.write("audit.py", "repository-only")
        self.write("image.png", "illustration")
        self.write("scripts/old.py", "historically public")
        self.write("publish-extra.json", json.dumps({"extra":{"scripts/old.py": "Pre-existing public URL"}, "release_holds":{}}))
        self.write("index.html", '<img src="/image.png">')
        subprocess.run(["git", "add", "--", "."], cwd=self.root, check=True)

    def write(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def test_build_and_withdrawal(self):
        target = self.root.parent / "output"
        selected = build(self.root, target)
        self.assertIn("image.png", selected)
        self.assertIn("scripts/old.py", selected)
        self.assertNotIn("audit.py", selected)
        self.assertEqual((target / "image.png").read_text(), "illustration")
        self.assertNotIn("scripts/old.py", select(self.root, withdraw_internal=True))
        self.write("index.html", '<a href="/scripts/old.py">Maintenance source</a>')
        with self.assertRaisesRegex(ValueError, "references"):
            select(self.root, withdraw_internal=True)

    def test_broken_reference_fails_before_install(self):
        self.write("index.html", '<img src="/missing.png">')
        target = self.root.parent / "output"
        with self.assertRaisesRegex(ValueError, "missing.png"):
            build(self.root, target)
        self.assertFalse(target.exists())

    def test_repository_files_and_private_paths_rejected(self):
        for invalid in ("audit.py", ".gitignore", ".github/example", "CV/profile", "vault-notes.md", "../secret", "publish-extra.json"):
            with self.subTest(invalid=invalid):
                self.write("publish-extra.json", json.dumps({"extra":{invalid:"test"}, "release_holds":{}}))
                with self.assertRaises(ValueError):
                    select(self.root)

    def test_reject_untracked_page_and_symbolic_link(self):
        self.write("draft.html", "draft")
        with self.assertRaisesRegex(ValueError, "untracked"):
            select(self.root)
        (self.root / "draft.html").unlink()
        (self.root / "image.png").unlink()
        (self.root / "image.png").symlink_to(self.root / "index.html")
        with self.assertRaisesRegex(ValueError, "missing references"):
            select(self.root)


if __name__ == "__main__":
    unittest.main()

