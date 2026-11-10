"""The manual gate reports child failures and skips and never dispatches live checks by default."""

import contextlib
import csv
import io
import runpy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from check_all import commands, run

ROOT = Path(__file__).resolve().parents[1]


class RunnerTests(unittest.TestCase):
    def test_statuses_and_network_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            for name, program in {
                "test_ok.py": "print('healthy')",
                "check_bad.py": "raise SystemExit('test failure')",
                "check_skip.py": "print('SKIP: fixture intentionally absent')",
                "check_site_live.py": "raise SystemExit('must never execute offline')",
            }.items():
                (scripts / name).write_text(program)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run(root, output=root / "results.csv"), 1)
            with (root / "results.csv").open() as stream:
                results = {
                    Path(r["check"]).stem: r["status"] for r in csv.DictReader(stream)
                }
            self.assertEqual(
                results,
                {
                    "test_ok": "PASS",
                    "check_bad": "FAIL",
                    "check_skip": "SKIP",
                    "check_site_live": "SKIP",
                },
            )
            steps = {
                name: (args, reason)
                for name, args, reason in commands(
                    root, True, live_report=root / "urls.json"
                )
            }
            args, reason = steps["scripts/check_site_live.py"]
            self.assertEqual(args[-3:], ["--live", "--json", str(root / "urls.json")])
            self.assertFalse(reason)

    def test_gallery_must_still_pass_its_own_checker(self):
        steps = {
            name: (args, reason)
            for name, args, reason in commands(ROOT, False, Path("example.json"))
        }
        self.assertTrue(steps["scripts/check_new_article_titles.py"][1])
        args, reason = steps["scripts/check_new_carousel_titles.py"]
        self.assertFalse(reason)
        self.assertEqual(args[-2:], ["--receipt", "example.json"])

    def test_generated_file_drift_fails_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "css").mkdir()
            for name in ("premium.css", "editorial.css", "refinement.css"):
                (root / "css" / name).write_text("a { color: red; }")
            style = root / "css/site.css"
            style.write_text("broken")
            script = root / "scripts/build_styles.py"
            shutil.copyfile(ROOT / "scripts" / script.name, script)
            result = subprocess.run(
                [sys.executable, str(script), "--check"], capture_output=True
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(style.read_text(), "broken")
            pdf = root / "example.pdf"
            pdf.write_bytes(b"%PDF synthetic negative control")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_facts_sheet_pdf.py"),
                    "--check",
                    str(pdf),
                    str(pdf),
                ],
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(pdf.read_bytes(), b"%PDF synthetic negative control")

    def test_localized_outputs_are_compared_without_writing(self):
        for source, target in [
            ("build_locales.py", "fa/index.html"),
            ("build_guide_locales.py", "js/decision-guide-fa.js"),
        ]:
            script = ROOT / "scripts" / source
            original = Path.read_text

            def edited(path, *args, **kwargs):
                value = original(path, *args, **kwargs)
                return value + "fixture edit" if path == ROOT / target else value

            with (
                self.subTest(source=source),
                patch.object(Path, "read_text", edited),
                patch.object(
                    Path, "write_text", side_effect=AssertionError("check wrote a file")
                ),
                patch.object(sys, "argv", [str(script), "--check"]),
            ):
                with self.assertRaisesRegex(SystemExit, "STALE"):
                    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    unittest.main()
