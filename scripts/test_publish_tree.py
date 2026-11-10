"""Offline fixtures for the manual publish allowlist."""
from pathlib import Path
import json
import io
from contextlib import redirect_stdout
from unittest.mock import patch
import publish
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
        self.write("sitemap.xml", "<urlset><url><loc>https://a-samadi.com/</loc></url></urlset>")
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

    def test_manual_publisher_uses_an_orphan_then_fast_forwards(self):
        remote = self.root.parent / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.STDOUT).decode().strip()
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        git("branch", "-M", "main")
        git("commit", "-qm", "Initial fixture")
        git("remote", "add", "origin", str(remote))
        git("push", "-qu", "origin", "main")
        with patch.object(publish, "ROOT", self.root), redirect_stdout(io.StringIO()) as output:
            publish.publish()
            first = git("rev-parse", "origin/site")
            self.assertEqual(git("rev-list", "--parents", "-1", first), first)
            self.assertNotIn("audit.py", git("ls-tree", "-r", "--name-only", first).splitlines())
            self.write("image.png", "second")
            git("commit", "-qam", "Update fixture image")
            git("push", "-q", "origin", "main")
            publish.publish()
            second = git("rev-parse", "origin/site")
            self.assertEqual(git("rev-parse", second + "^"), first)
            self.assertEqual(git("show", second + ":image.png"), "second")
            publish.publish()
            self.assertEqual(git("rev-parse", "origin/site"), second)
            manifest = json.loads((self.root / "publish-extra.json").read_text())
            manifest["release_holds"] = {"a-served-path": "owner decision required"}
            self.write("publish-extra.json", json.dumps(manifest))
            git("commit", "-qam", "Record fixture hold")
            git("push", "-q", "origin", "main")
            with self.assertRaisesRegex(ValueError, "a-served-path"):
                publish.publish()
            self.assertEqual(git("rev-parse", "origin/site"), second)
        self.assertIn("source[branch]=site", output.getvalue())
        self.assertEqual(git("branch", "--show-current"), "main")

    def test_broken_reference_fails_before_install(self):
        self.write("index.html", '<img src="/missing.png">')
        target = self.root.parent / "output"
        with self.assertRaisesRegex(ValueError, "missing.png"):
            build(self.root, target)
        self.assertFalse(target.exists())

    def test_explicit_forbidden_reference_is_not_silently_skipped(self):
        self.write("index.html", '<a href="/CV/file.pdf">Private file</a>')
        with self.assertRaisesRegex(ValueError, "forbidden public path"):
            select(self.root)

    def test_repository_files_and_private_paths_rejected(self):
        for invalid in ("audit.py", ".gitignore", ".github/example", "CV/profile", "vault-notes.md", "../secret", "publish-extra.json"):
            with self.subTest(invalid=invalid):
                self.write("publish-extra.json", json.dumps({"extra":{invalid:"test"}, "release_holds":{}}))
                with self.assertRaises(ValueError):
                    select(self.root)

    def test_reject_untracked_page_and_symbolic_link(self):
        self.write("unlinked.html", "private draft")
        subprocess.run(["git", "add", "--", "unlinked.html"], cwd=self.root, check=True)
        self.assertNotIn("unlinked.html", select(self.root))
        self.write("draft.html", "draft")
        self.write("index.html", '<a href="/draft.html">Untracked</a>')
        with self.assertRaisesRegex(ValueError, "untracked"):
            select(self.root)
        (self.root / "draft.html").unlink()
        self.write("index.html", '<img src="/image.png">')
        (self.root / "image.png").unlink()
        (self.root / "image.png").symlink_to(self.root / "index.html")
        with self.assertRaisesRegex(ValueError, "missing references"):
            select(self.root)


if __name__ == "__main__":
    unittest.main()
