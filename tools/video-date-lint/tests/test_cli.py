# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ahmadreza Samadi
"""Behavioral subprocess fixtures; inputs are synthetic and checked for preservation."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "video_datetime_lint.py"
NOW = "2026-10-10T00:00:00Z"
FILM = "https://example.invalid/film.mp4"


class CliFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fixture-", dir=Path(__file__).parent)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def html(self, name, stamp, identity=FILM, opening='<script type="application/ld+json">'):
        node = {"@type": "VideoObject", "uploadDate": stamp}
        if identity is not None:
            node["contentUrl"] = identity
        path = self.root / name
        path.write_text("<!doctype html>" + opening + json.dumps(node) + "</script>", encoding="utf-8")
        return path

    def sitemap(self, stamp=None, identity=FILM):
        date = "" if stamp is None else "<video:publication_date>" + stamp + "</video:publication_date>"
        path = self.root / "videos.xml"
        path.write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                        'xmlns:video="http://www.google.com/schemas/sitemap-video/1.1"><url>'
                        '<loc>https://example.invalid/watch</loc><video:video><video:content_loc>'
                        + identity + '</video:content_loc>' + date + '</video:video></url></urlset>', encoding="utf-8")
        return path

    def run_cli(self, *arguments, output_encoding=None):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob("*") if p.is_file()}
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        if output_encoding is not None:
            env["PYTHONIOENCODING"] = output_encoding
        result = subprocess.run([sys.executable, str(CLI), "--now", NOW, "--format", "json", *map(str, arguments)],
                                capture_output=True, text=True, env=env, check=False)
        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after, "CLI must preserve every input and create no files")
        self.assertEqual(result.stderr, "", result.stderr)
        body = json.loads(result.stdout)
        self.assertEqual(body["exit_code"], result.returncode)
        return result.returncode, body, result.stdout

    def test_original_date_only_warning_and_strict_policy(self):
        file = self.html("before.html", "2026-10-05")
        code, body, _ = self.run_cli(file)
        self.assertEqual(code, 0)
        self.assertEqual([(d["code"], d["severity"]) for d in body["diagnostics"]], [("date_without_time", "warning")])
        code, body, _ = self.run_cli(file, "--strict-datetime")
        self.assertEqual(code, 1)
        self.assertEqual(body["counts"]["errors"], 1)

    def test_missing_timezone_is_not_guessed(self):
        file = self.html("no-zone.html", "2026-10-05T18:47:15")
        code, body, _ = self.run_cli(file)
        self.assertEqual(code, 0)
        self.assertEqual(body["diagnostics"][0]["code"], "missing_timezone")
        self.assertEqual(self.run_cli(file, "--strict-datetime")[0], 1)

    def test_valid_offsets_z_fraction_and_impossible_values(self):
        for stamp in ["2026-10-05T18:47:15+03:30", "2026-10-05T15:17:15Z", "2026-10-05T08:17:15-07:00", "2026-10-05T15:17:15.123456Z", NOW]:
            with self.subTest(valid=stamp):
                file = self.html("date.html", stamp)
                code, body, _ = self.run_cli(file, "--strict-datetime")
                self.assertEqual(code, 0)
                self.assertEqual(body["diagnostics"], [])
        for stamp in [None, 20261005, "", "2026-02-30T10:00:00Z", "2026-10-05T24:00:00Z", "2026-10-05T10:60:00Z", "2026-10-05T10:00:60Z", "2026-10-05T18:47:15+03:99", "2026-10-05T18:47:15-00:99", "2026-10-05T18:47:15+24:00"]:
            with self.subTest(invalid=stamp):
                file = self.html("date.html", stamp)
                code, body, _ = self.run_cli(file)
                self.assertEqual(code, 1)
                self.assertEqual(body["counts"]["errors"], 1)

    def test_calendar_boundaries_and_future_clock_injection(self):
        self.assertEqual(self.run_cli(self.html("leap.html", "2024-02-29T12:00:00Z"))[0], 0)
        self.assertEqual(self.run_cli(self.html("not-leap.html", "2025-02-29T12:00:00Z"))[0], 1)
        file = self.html("future.html", "2026-10-10T00:00:01Z")
        code, body, _ = self.run_cli(file)
        self.assertEqual(code, 1)
        self.assertEqual(body["diagnostics"][0]["code"], "future_publication_date")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, str(CLI), str(file), "--now", "2026-10-10T00:00:02Z", "--format", "json"], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["counts"]["errors"], 0)

    def test_graph_nested_list_and_attribute_variants(self):
        node = {"@type": ["Thing", "https://schema.org/VideoObject"], "uploadDate": "2026-10-05T15:17:15Z", "contentUrl": FILM}
        data = [{"@graph": [{"video": node}]}, {"@type": "Person", "name": "Synthetic"}]
        file = self.root / "graph.htm"
        file.write_text("<SCRIPT data-test='yes' TYPE = 'application/ld+json'>" + json.dumps(data) + "</SCRIPT>", encoding="utf-8")
        code, body, _ = self.run_cli(file)
        self.assertEqual(code, 0)
        self.assertEqual(body["counts"]["video_objects"], 1)
        self.assertEqual(body["counts"]["jsonld_blocks"], 1)

    def test_malformed_and_ambiguous_json_are_input_failures(self):
        for payload in ['{"@type":"VideoObject",', '{"uploadDate":"2026-10-05","uploadDate":"2026-10-06"}', '{"x": NaN}']:
            with self.subTest(payload=payload):
                file = self.root / "bad.html"
                file.write_text('<script type="application/ld+json">' + payload + '</script>', encoding="utf-8")
                code, body, _ = self.run_cli(file)
                self.assertEqual(code, 2)
                self.assertEqual(body["diagnostics"][0]["code"], "invalid_jsonld")
        file.write_text('<script type="application/ld+json">{}', encoding="utf-8")
        self.assertEqual(self.run_cli(file)[0], 2)

    def test_scalar_jsonld_and_explicit_empty_document_distinction(self):
        file = self.root / "root.html"
        for value in [True, 7, "scalar"]:
            with self.subTest(unsupported=value):
                file.write_text('<script type="application/ld+json">' + json.dumps(value) + '</script>', encoding="utf-8")
                code, body, _ = self.run_cli(file)
                self.assertEqual(code, 2)
                self.assertEqual(body["diagnostics"][0]["code"], "unsupported_jsonld_document")
                self.assertEqual(body["counts"]["video_objects"], 0)
        for value in [None, {}, []]:
            with self.subTest(empty=value):
                file.write_text('<script type="application/ld+json">' + json.dumps(value) + '</script>', encoding="utf-8")
                code, body, _ = self.run_cli(file)
                self.assertEqual(code, 0)
                self.assertEqual(body["diagnostics"][0]["code"], "empty_jsonld_document")
                self.assertEqual(self.run_cli(file, "--require-video")[0], 1)

    def test_utc_clock_overflow_is_usage_error_without_traceback(self):
        file = self.html("video.html", "2026-10-05T15:17:15Z")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for clock in ["0001-01-01T00:00:00+23:59", "9999-12-31T23:59:59-23:59"]:
            with self.subTest(clock=clock):
                result = subprocess.run([sys.executable, str(CLI), str(file), "--now", clock, "--format", "json"], capture_output=True, text=True, env=env)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("UTC datetime range", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_repeated_identity_compares_instants_not_literals(self):
        a = self.html("a.html", "2026-10-05T18:47:15+03:30")
        b = self.html("b.html", "2026-10-05T08:17:15-07:00")
        c = self.html("c.html", "2026-10-05T15:17:15Z")
        code, body, _ = self.run_cli(c, b, a)
        self.assertEqual(code, 0)
        self.assertEqual(body["counts"]["repeated_video_comparisons"], 2)
        b = self.html("b.html", "2026-10-05T15:17:16Z")
        code, body, _ = self.run_cli(a, b)
        self.assertEqual(code, 1)
        self.assertEqual(body["diagnostics"][0]["code"], "repeated_video_mismatch")
        self.assertIn(str(a), body["diagnostics"][0]["message"])
        other = self.html("other.html", "2026-10-05T15:17:16Z", "https://example.invalid/another-film.mp4")
        self.assertEqual(self.run_cli(a, other)[0], 0)

    def test_cross_zone_calendar_rollover_equivalence(self):
        a = self.html("a.html", "2026-10-05T01:00:00+03:30")
        b = self.html("b.html", "2026-10-04T21:30:00Z")
        self.assertEqual(self.run_cli(a, b)[0], 0)

    def test_sitemap_optional_date_only_and_strict_presence(self):
        html = self.html("video.html", "2026-10-05T15:17:15Z")
        xml = self.sitemap()
        code, body, _ = self.run_cli(html, "--sitemap", xml)
        self.assertEqual(code, 0)
        self.assertEqual(body["counts"]["sitemap_videos"], 1)
        self.assertEqual(body["counts"]["skipped_consistency_checks"], 1)
        self.assertEqual(body["diagnostics"], [])
        self.assertEqual(self.run_cli(html, "--sitemap", xml, "--require-sitemap-dates")[0], 1)
        xml = self.sitemap("2026-10-05")
        code, body, _ = self.run_cli(html, "--sitemap", xml)
        self.assertEqual(code, 0)
        self.assertEqual(body["diagnostics"], [])
        self.assertEqual(self.run_cli(html, "--sitemap", xml, "--strict-datetime")[0], 1)

    def test_sitemap_instant_match_mismatch_and_partial_scan(self):
        html = self.html("video.html", "2026-10-05T15:17:15Z")
        xml = self.sitemap("2026-10-05T18:47:15+03:30")
        code, body, _ = self.run_cli(html, "--sitemap", xml)
        self.assertEqual(code, 0)
        self.assertEqual(body["counts"]["sitemap_comparisons"], 1)
        xml = self.sitemap("2026-10-05T15:17:16Z")
        code, body, _ = self.run_cli(html, "--sitemap", xml)
        self.assertEqual(code, 1)
        self.assertEqual(body["diagnostics"][0]["code"], "sitemap_video_mismatch")
        xml = self.sitemap("2026-10-05T15:17:15Z", "https://example.invalid/unseen.mp4")
        code, body, _ = self.run_cli(html, "--sitemap", xml)
        self.assertEqual(code, 0)
        self.assertEqual(body["diagnostics"][0]["code"], "unmatched_sitemap_video")

    def test_malformed_xml_missing_input_and_zero_count(self):
        xml = self.root / "bad.xml"
        xml.write_text("<urlset>", encoding="utf-8")
        code, body, _ = self.run_cli("--sitemap", xml)
        self.assertEqual(code, 2)
        self.assertEqual(body["diagnostics"][0]["code"], "invalid_sitemap")
        self.assertEqual(self.run_cli(self.root / "absent.html")[0], 2)
        file = self.root / "ordinary.html"
        file.write_text("<p>Ordinary document</p>", encoding="utf-8")
        code, body, _ = self.run_cli(file)
        self.assertEqual(code, 0)
        self.assertEqual(body["counts"]["video_objects"], 0)
        self.assertEqual(self.run_cli(file, "--require-video")[0], 1)

    def test_unknown_xml_declared_encoding_is_input_failure(self):
        file = self.root / "unknown-encoding.xml"
        file.write_bytes(b'<?xml version="1.0" encoding="not-an-encoding"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>')
        code, body, _ = self.run_cli("--sitemap", file)
        self.assertEqual(code, 2)
        self.assertEqual(body["counts"]["errors"], 1)
        self.assertEqual(body["diagnostics"][0]["code"], "invalid_sitemap")
        self.assertIn("unknown encoding", body["diagnostics"][0]["message"])

    def test_json_lone_surrogate_and_ascii_stream_are_reportable(self):
        file = self.html("Café-مثال.html", "\ud800")
        for encoding in [None, "ascii:strict"]:
            with self.subTest(output_encoding=encoding):
                code, body, output = self.run_cli(file, output_encoding=encoding)
                self.assertEqual(code, 1)
                self.assertEqual(body["diagnostics"][0]["code"], "invalid_publication_date")
                self.assertEqual(body["diagnostics"][0]["value"], "\ud800")
                self.assertEqual(body["diagnostics"][0]["path"], str(file))
                self.assertTrue(output.isascii())
        file.write_text('<script type="application/ld+json">{"\\ud800":1,"\\ud800":2}</script>', encoding="utf-8")
        code, body, output = self.run_cli(file, output_encoding="ascii:strict")
        self.assertEqual(code, 2)
        self.assertEqual(body["diagnostics"][0]["code"], "invalid_jsonld")
        self.assertIn("\ud800", body["diagnostics"][0]["message"])
        self.assertTrue(output.isascii())

    def test_text_diagnostics_escape_nonencodable_path_and_message(self):
        file = self.root / "Café-مثال.html"
        file.write_text('<script type="application/ld+json">{"\\ud800":1,"\\ud800":2}</script>', encoding="utf-8")
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        for encoding in ["utf-8:strict", "ascii:strict"]:
            with self.subTest(output_encoding=encoding):
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING=encoding)
                result = subprocess.run([sys.executable, str(CLI), str(file), "--now", NOW], capture_output=True, text=True, env=env)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr, "")
                self.assertIn("invalid_jsonld", result.stdout)
                self.assertIn("duplicate object key: \\ud800", result.stdout)
                self.assertIn("exit 2", result.stdout)
                if encoding.startswith("ascii"):
                    self.assertTrue(result.stdout.isascii())
                    self.assertIn("Caf\\xe9", result.stdout)
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), before)

    def test_directory_dedup_stable_json_and_text_output(self):
        a = self.html("a.html", "2026-10-05T15:17:15Z")
        self.html("b.html", "2026-10-05T15:17:15Z")
        code, body, first = self.run_cli(self.root, a)
        self.assertEqual(code, 0)
        self.assertEqual(body["counts"]["html_files"], 2)
        self.assertEqual(first, self.run_cli(a, self.root)[2])
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, str(CLI), str(a), "--now", NOW], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("1 VideoObjects", result.stdout)
        self.assertIn("exit 0", result.stdout)
        bad_clock = subprocess.run([sys.executable, str(CLI), str(a), "--now", "2026-10-10T00:00:00"], capture_output=True, text=True, env=env)
        self.assertEqual(bad_clock.returncode, 2)
        self.assertIn("explicit timezone", bad_clock.stderr)


if __name__ == "__main__":
    unittest.main()
