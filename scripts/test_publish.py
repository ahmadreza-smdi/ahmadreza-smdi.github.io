"""Offline failure drills, using a new local origin and a fake Pages service for every test."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import publish
import test_publish_tree as fixtures


class PublishFailureTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.PublishTreeTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.write = fixture.write
        self.scratch = self.root.parent
        self.remote = self.scratch / "origin.git"
        self.git("init", "-q", "--bare", str(self.remote))
        self.git("config", "user.name", "Release fixture")
        self.git("config", "user.email", "release@example.invalid")
        self.git("branch", "-M", "main")
        self.git("commit", "-qm", "fixture")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-qu", "origin", "main")
        self.enterContext(patch.object(publish, "ROOT", self.root))

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, stderr=subprocess.PIPE).strip()

    def run_publish(self, **options):
        output = io.StringIO()
        with redirect_stdout(output):
            publish.publish(**options)
        return output.getvalue()

    def site(self):
        return self.git("ls-remote", "origin", "refs/heads/site").split()

    def advance(self, changed):
        self.write("image.png", changed)
        self.git("commit", "-qam", changed)
        self.git("push", "-q", "origin", "main")

    def test_dirty_and_protected_staging(self):
        self.write("image.png", "local")
        with self.assertRaisesRegex(ValueError, "Tracked or staged edits"):
            self.run_publish()
        for path in ("CV/synthetic.txt", "vault-synthetic.txt"):
            with self.subTest(path=path):
                self.write(path, "synthetic fixture")
                self.git("add", "--", path)
                with self.assertRaisesRegex(ValueError, "Protected path staged"):
                    self.run_publish()
                self.git("restore", "--staged", "--", path)
        self.assertFalse(self.site())

    def test_wrong_branch_and_main_ahead_or_behind(self):
        self.git("switch", "-qc", "fixture")
        with self.assertRaisesRegex(ValueError, "main checkout"):
            self.run_publish()
        self.git("switch", "-q", "main")
        self.write("image.png", "ahead")
        self.git("commit", "-qam", "ahead")
        with self.assertRaisesRegex(ValueError, "Local main differs"):
            self.run_publish()
        self.git("push", "-q", "origin", "main")
        original = self.git("rev-parse", "HEAD")
        self.git("switch", "-qc", "simulated-other-checkout")
        self.git("commit", "--allow-empty", "-qm", "remote advance")
        self.git("push", "-q", "origin", "HEAD:main")
        self.git("switch", "-q", "main")
        with self.assertRaisesRegex(ValueError, "Local main differs"):
            self.run_publish()
        self.assertEqual(self.git("rev-parse", "HEAD"), original)
        self.assertFalse(self.site())

    def test_broken_reference(self):
        self.write("index.html", '<img src="/missing.png">')
        self.git("commit", "-qam", "missing image fixture")
        self.git("push", "-q", "origin", "main")
        with self.assertRaisesRegex(ValueError, "index.html -> missing.png"):
            self.run_publish()
        self.assertFalse(self.site())

    def test_remote_site_changed(self):
        self.run_publish()
        first = self.site()[0]
        second = self.git("commit-tree", first+"^{tree}", "-p", first, "-m", "remote publisher")
        self.git("--git-dir="+str(self.remote), "fetch", str(self.root), second)
        self.git("--git-dir="+str(self.remote), "update-ref", "refs/heads/site", second, first)
        with self.assertRaisesRegex(ValueError, "Remote site differs"):
            self.run_publish()
        self.assertEqual(self.site()[0], second)

    def test_lost_connection_before_or_after_acceptance(self):
        original = publish.git
        for accepted in (False, True):
            def interrupted(*args, **kwargs):
                if args[0] == "push":
                    if accepted:
                        original(*args, **kwargs)
                    raise subprocess.CalledProcessError(128, ["git", "push"])
                return original(*args, **kwargs)
            with self.subTest(accepted=accepted), patch.object(publish, "git", interrupted):
                if accepted:
                    self.assertIn("Confirmed the expected commit", self.run_publish())
                else:
                    with self.assertRaisesRegex(ValueError, "Site push failed"):
                        self.run_publish()
                    self.assertFalse(self.site())
        first = self.site()
        self.run_publish()
        self.assertEqual(self.site(), first)

    def test_repeat_dry_run_rollback_and_no_archive_drive(self):
        self.assertFalse(str(self.root).startswith("/Volumes/"))
        with patch.dict(os.environ, {"TMPDIR":str(self.scratch)}):
            self.assertIn("Dry run verified", self.run_publish(dry_run=True))
            self.assertFalse(self.site())
            self.run_publish()
            first = self.site()[0]
            self.run_publish()
            self.assertEqual(self.site()[0], first)
            with self.assertRaisesRegex(ValueError, "exactly one parent"):
                self.run_publish(rollback=True)
            self.advance("second version")
            self.run_publish()
            second = self.site()[0]
            self.run_publish(rollback=True)
            rollback = self.site()[0]
            self.assertEqual(self.git("rev-parse", rollback+"^"), second)
            self.assertEqual(self.git("rev-parse", rollback+"^{tree}"), self.git("rev-parse", first+"^{tree}"))

    def deployment(self, mode, interrupt=None):
        fake = self.scratch / "gh"
        fake.write_text(f"#!{sys.executable}\n" + """import os,sys,time,signal
from pathlib import Path
p=Path(os.environ['FAKE_LOG'])
args=sys.argv[1:]
with p.open('a') as f: print(' '.join(args),file=f)
if 'build_type=legacy' in args:
    Path(str(p)+'.worker').write_text(str(os.getppid()))
if args[-1]=='build_type=workflow':
    Path(str(p)+'.restored').touch()
if '/pages/builds/latest' in ' '.join(args):
    mode=os.environ['FAKE_RESULT']
    if mode=='hold':
        time.sleep(.4)
        mode='built'
    print(mode, 'fixturecommit')
""")
        fake.chmod(0o755)
        sleep = self.scratch / "sleep"
        sleep.write_text("#!/bin/sh\nexit 0\n")
        sleep.chmod(0o755)
        log = self.scratch / "calls"
        body = publish.deploy_command("fixturecommit").split("\n",1)[1].rsplit("\nPAGES",1)[0]
        script = self.scratch / "deployment.sh"
        script.write_text(body)
        env = dict(os.environ, PATH=str(self.scratch)+":"+os.environ["PATH"], PAGES_GH=str(fake),
                   FAKE_LOG=str(log), FAKE_RESULT=mode)
        proc = subprocess.Popen(["sh","-eu",str(script)], env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True, text=True)
        if interrupt:
            marker = Path(str(log)+".worker")
            deadline = time.monotonic()+5
            while not marker.exists() and time.monotonic()<deadline:
                time.sleep(.01)
            self.assertTrue(marker.is_file())
            who, sig = interrupt
            os.kill(proc.pid if who=="parent" else int(marker.read_text()), sig)
        output = proc.communicate(timeout=18)[0]
        self.assertTrue(Path(str(log)+".restored").exists(), output)
        calls = log.read_text().splitlines()
        self.assertTrue("build_type=workflow" in calls[-1], calls[-3:])
        self.assertTrue(any("source[branch]=site" in line for line in calls))
        return proc.returncode, output

    def test_native_build_success(self):
        code, output = self.deployment("built")
        self.assertEqual(code, 0)
        self.assertIn("Pages built", output)

    def test_native_build_error(self):
        code, output = self.deployment("errored")
        self.assertNotEqual(code, 0)
        self.assertIn("Pages build failed", output)

    def test_native_build_timeout(self):
        code, output = self.deployment("building")
        self.assertNotEqual(code, 0)
        self.assertIn("Timed out", output)

    def test_native_ctrl_c(self):
        self.assertNotEqual(self.deployment("hold", ("parent",signal.SIGINT))[0], 0)

    def test_native_killed_worker(self):
        self.assertNotEqual(self.deployment("hold", ("worker",signal.SIGKILL))[0], 0)

    def test_native_killed_parent(self):
        self.assertNotEqual(self.deployment("hold", ("parent",signal.SIGKILL))[0], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
