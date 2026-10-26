from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location("online_publish", Path(__file__).with_name("publish.py"))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PublicationGuards(unittest.TestCase):
    def setUp(self):
        self.due = datetime(2026, 10, 23, 21, tzinfo=p.ZONE)
        self.row = {"publish_at": self.due.isoformat(), "sha256": "a" * 64}
        self.config = {"schema": 1, "timezone": "Asia/Tehran", "daily_count": 1,
                       "local_slot": "21:00", "films": [self.row]}

    def test_future_and_stale_never_publish(self):
        for now in [self.due - timedelta(seconds=1), self.due + timedelta(minutes=30, seconds=1),
                    self.due + timedelta(days=365)]:
            self.assertEqual([], p.due_rows(self.config, now))

    def test_due_and_bounded_retry(self):
        for delta in [0, 10, 20, 30]:
            self.assertEqual([self.row], p.due_rows(self.config, self.due + timedelta(minutes=delta)))

    def test_duplicate_day_rejected(self):
        self.config["films"].append(dict(self.row))
        with self.assertRaises(AssertionError):
            p.validate_schedule(self.config)

    def test_wrong_cadence_or_timezone_rejected(self):
        for key, value in [("daily_count", 2), ("local_slot", "10:00"), ("timezone", "UTC")]:
            bad = dict(self.config, **{key: value})
            with self.assertRaises(AssertionError):
                p.validate_schedule(bad)

    def test_morning_slot_rejected(self):
        self.row["publish_at"] = self.due.replace(hour=10).isoformat()
        with self.assertRaises(AssertionError):
            p.validate_schedule(self.config)

    def test_cloud_prewarm_is_today_only_bounded_and_never_early(self):
        self.assertEqual(7200, p.next_wait_seconds(self.config, self.due - timedelta(hours=2)))
        for now in [self.due - timedelta(hours=4), self.due, self.due + timedelta(seconds=1), self.due - timedelta(days=1)]:
            self.assertEqual(0, p.next_wait_seconds(self.config, now))

    def test_private_preparation_does_not_make_future_content_due(self):
        early = self.due - timedelta(hours=2)
        self.assertEqual([self.row], p.preparation_rows(self.config, early, True))
        self.assertEqual([], p.due_rows(self.config, early))
        self.assertEqual([], p.preparation_rows(self.config, early, False))
        for now in [self.due - timedelta(hours=4), self.due - timedelta(days=1),
                    self.due + timedelta(minutes=31)]:
            self.assertEqual([], p.preparation_rows(self.config, now, True))

    def test_preflight_stays_private_and_expired_wait_cannot_copy_or_push(self):
        for late in [False, True]:
            with self.subTest(late=late), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "writing").mkdir()
                row = dict(self.row, key="2026-10-23")
                config = dict(self.config, films=[row])
                clock = [self.due - timedelta(hours=2)]
                staged = []
                pushed = []

                class Clock(datetime):
                    @classmethod
                    def now(cls, zone=None):
                        return clock[0]

                def prepare(site, folder, review, stamp, record):
                    self.assertFalse((root / "writing/new.html").exists())
                    (site / "writing/new.html").write_text("reviewed private film")
                    return ["writing/new.html"]

                def checks(site):
                    self.assertTrue((site / "writing/new.html").exists())
                    self.assertFalse((root / "writing/new.html").exists())
                    return 28

                def wait(config, rows):
                    self.assertFalse((root / "writing/new.html").exists())
                    self.assertEqual([], pushed)
                    clock[0] = self.due + timedelta(minutes=31 if late else 0)

                def run(args, *unused, **kw):
                    if args[:2] == ["git", "rev-parse"]:
                        return "base"
                    if args[:2] == ["git", "add"]:
                        staged[:] = args[3:]
                    if args == ["git", "diff", "--cached", "--name-only"]:
                        return "\n".join(staged)
                    if args[:2] == ["git", "push"]:
                        self.assertTrue(p.due_rows(config, clock[0]))
                        pushed.append(True)
                    return ""

                with patch.multiple(p, ROOT=root, read=lambda path: config, datetime=Clock,
                                    run=run, prepare=prepare, checks=checks,
                                    obtain=lambda *args: (root, {"slug": "new"}),
                                    wait_until_due=wait, verify_live=lambda *args: None), \
                        patch("sys.argv", ["publish.py", "--wait-for-slot"]):
                    if late:
                        with self.assertRaisesRegex(ValueError, "Release window expired"):
                            p.main()
                        self.assertFalse((root / "writing/new.html").exists())
                        self.assertEqual([], pushed)
                    else:
                        p.main()
                        self.assertTrue((root / "writing/new.html").exists())
                        self.assertEqual([True], pushed)

    def test_late_job_after_midnight_is_a_missed_slot_not_green_noop(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td)
            row = dict(self.row, key="2026-10-23")
            config = dict(self.config, films=[row])
            self.assertEqual([row["key"]], p.missed_rows(config, self.due + timedelta(hours=4), site))
            self.assertEqual([], p.missed_rows(config, self.due - timedelta(seconds=1), site))
            path = site / "data/film-publications/2026-10-23.json"
            path.parent.mkdir(parents=True)
            path.write_text("{}")
            self.assertEqual([], p.missed_rows(config, self.due + timedelta(hours=4), site))

    def test_catchup_requires_exact_owner_receipt_and_original_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td)
            (site / "scripts/online_films").mkdir(parents=True)
            (site / "data/film-publications").mkdir(parents=True)
            row = dict(self.row, key="2026-10-23")
            (site / "scripts/online_films/schedule.json").write_text(json.dumps(dict(self.config, films=[row])))
            receipt = {"slug": "escrow", "bundle_sha256": row["sha256"], "scheduled_at": row["publish_at"],
                       "catch_up_authorization": {"original_date": row["key"], "owner_direct_request": True, "evidence_sha256": "b" * 64}}
            path = site / "data/film-publications/2026-10-23.json"
            path.write_text(json.dumps(receipt))
            self.assertTrue(p.authorized_catchup_page(site, "escrow", self.due + timedelta(days=2)))
            self.assertFalse(p.authorized_catchup_page(site, "escrow", self.due))
            receipt["bundle_sha256"] = "c" * 64
            path.write_text(json.dumps(receipt))
            self.assertFalse(p.authorized_catchup_page(site, "escrow", self.due + timedelta(days=2)))

    def bundle(self, td, ready=True, extra=None):
        a = Path(td) / "bundle.zip"
        content = b"reviewed fixture"
        review = {"files": {"fixture.txt": hashlib.sha256(content).hexdigest()},
                  "all_plan6_video_checks_passed": ready, "independent_article_review": True,
                  "native_human_review_claimed": False}
        with zipfile.ZipFile(a, "w") as z:
            z.writestr("Review.json", json.dumps(review))
            z.writestr("fixture.txt", content)
            if extra:
                z.writestr(extra, "unexpected")
        return a

    def test_valid_bundle_and_changed_archive(self):
        with tempfile.TemporaryDirectory() as td:
            a = self.bundle(td)
            p.unpack(a, Path(td) / "valid", p.sha(a))
            with self.assertRaises(ValueError):
                p.unpack(a, Path(td) / "bad", "0" * 64)

    def test_unready_media_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a = self.bundle(td, ready=False)
            with self.assertRaises(ValueError):
                p.unpack(a, Path(td) / "bad", p.sha(a))

    def test_unexpected_and_traversal_members_rejected(self):
        for extra in ["unexpected.txt", "../escape.txt", "/absolute.txt"]:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as td:
                a = self.bundle(td, extra=extra)
                with self.assertRaises(ValueError):
                    p.unpack(a, Path(td) / "bad", p.sha(a))

    def test_pages_fallback_requires_exact_sha_environment_and_latest_success(self):
        deployment = {"sha": "a" * 40, "environment": "github-pages"}
        self.assertTrue(p.successful_exact_deployment(deployment, [{"state": "success"}], "a" * 40))
        self.assertFalse(p.successful_exact_deployment(deployment, [{"state": "success"}], "b" * 40))
        self.assertFalse(p.successful_exact_deployment(dict(deployment, environment="preview"), [{"state": "success"}], "a" * 40))
        self.assertFalse(p.successful_exact_deployment(deployment, [{"state": "pending"}, {"state": "success"}], "a" * 40))

    def test_cloudflare_email_transform_preserves_exact_content(self):
        email = b"public@example.com"
        encoded = bytes([42, *[b ^ 42 for b in email]]).hex().encode()
        source = b'<p>Reviewed film</p><a href="mailto:' + email + b'">Contact</a>'
        served = source.replace(b"mailto:" + email, b"/cdn-cgi/l/email-protection#" + encoded)
        served += b'<script data-cfasync="false" src="/cdn-cgi/scripts/5c5dd728/cloudflare-static/email-decode.min.js"></script>'
        self.assertEqual(source, p.normalize_served_html(served))
        self.assertNotEqual(source, p.normalize_served_html(served.replace(b"Reviewed", b"Changed")))
        self.assertNotEqual(source, p.normalize_served_html(served + b"<script>unexpected()</script>"))

    def test_existing_film_blocks_second_daily_film(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td)
            (site / "writing").mkdir()
            data = {"@graph": [{"@type": "Article", "video": {"@id": "v"},
                                "datePublished": self.due.isoformat()}]}
            (site / "writing/existing.html").write_text('<script type="application/ld+json">' + json.dumps(data) + '</script>')
            with self.assertRaises(ValueError):
                p.refuse_existing_film_day(site, self.due)
            p.refuse_existing_film_day(site, self.due + timedelta(days=1))


if __name__ == "__main__":
    unittest.main()
