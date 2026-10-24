"""Publish one reviewed film at its due time; future bundles remain draft assets."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "scripts/online_films/schedule.json"
ZONE = timezone(timedelta(hours=3, minutes=30))
EXCLUDE = {".git", "__pycache__", ".DS_Store", "node_modules"}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def run(args, cwd=ROOT, output=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    if output:
        Path(output).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"Command failed: {args!r}\n{result.stdout[-3000:]}{result.stderr[-3000:]}")
    return result.stdout.strip()


def inventory(root):
    result = {}
    for parent, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in EXCLUDE)
        for name in sorted(files):
            if name in EXCLUDE:
                continue
            path = Path(parent) / name
            if path.is_symlink():
                raise ValueError("Symlink requires review")
            result[str(path.relative_to(root))] = sha(path)
    return result


def validate_schedule(config):
    assert config["schema"] == 1 and config["timezone"] == "Asia/Tehran"
    assert config["daily_count"] == 1 and config["local_slot"] == "21:00"
    dates = []
    for row in config["films"]:
        due = datetime.fromisoformat(row["publish_at"])
        assert due.utcoffset() == timedelta(hours=3, minutes=30)
        assert due.strftime("%H:%M:%S") == "21:00:00"
        assert len(row["sha256"]) == 64
        dates.append(due.date())
    assert dates == sorted(set(dates)), "At most one reviewed film per day"


def due_rows(config, now):
    return [r for r in config["films"]
            if datetime.fromisoformat(r["publish_at"]) <= now
            <= datetime.fromisoformat(r["publish_at"]) + timedelta(minutes=30)]


def next_wait_seconds(config, now):
    """Prewarm only today's reviewed slot, never an old slot or unbounded worker."""
    waits = [(datetime.fromisoformat(r["publish_at"]) - now).total_seconds()
             for r in config["films"]
             if datetime.fromisoformat(r["publish_at"]).date() == now.astimezone(ZONE).date()]
    return next((seconds for seconds in waits if 0 < seconds <= 3 * 3600), 0)


def missed_rows(config, now, site):
    return [r["key"] for r in config["films"]
            if now > datetime.fromisoformat(r["publish_at"]) + timedelta(minutes=30)
            and not (site / ("data/film-publications/" + r["key"] + ".json")).exists()]


def authorized_catchup_page(site, slug, due):
    # A separately owner-authorized missed family does not consume today's normal slot.
    # Only a committed receipt bound to an exact original schedule/bundle can do this.
    config_path = site / "scripts/online_films/schedule.json"
    if not config_path.exists():
        return False
    config = read(config_path)
    for row in config["films"]:
        receipt_path = site / ("data/film-publications/" + row["key"] + ".json")
        if not receipt_path.exists():
            continue
        receipt = read(receipt_path)
        authority = receipt.get("catch_up_authorization", {})
        if (receipt.get("slug") == slug and receipt.get("bundle_sha256") == row["sha256"]
                and receipt.get("scheduled_at") == row["publish_at"]
                and authority.get("original_date") == row["key"]
                and authority.get("owner_direct_request") is True
                and len(authority.get("evidence_sha256", "")) == 64
                and datetime.fromisoformat(row["publish_at"]).date() < due.date()):
            return True
    return False


def refuse_existing_film_day(site, due):
    for page in (site / "writing").glob("*.html"):
        for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page.read_text(), re.S):
            data = json.loads(raw)
            nodes = data.get("@graph", [data])
            for node in nodes:
                if node.get("@type") == "Article" and node.get("video") and node.get("datePublished"):
                    published = datetime.fromisoformat(node["datePublished"].replace("Z", "+00:00"))
                    if published.astimezone(ZONE).date() == due.astimezone(ZONE).date():
                        if authorized_catchup_page(site, page.stem, due):
                            continue
                        raise ValueError("This day already has a published film: " + page.name)


def unpack(archive, destination, expected):
    if sha(archive) != expected:
        raise ValueError("Frozen bundle checksum mismatch")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or sum(i.file_size for i in z.infolist()) > 500_000_000:
            raise ValueError("Unexpected bundle inventory or size")
        for info in z.infolist():
            p = Path(info.filename)
            if p.is_absolute() or ".." in p.parts or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError("Unsafe bundle member")
        z.extractall(destination)
    review = read(destination / "Review.json")
    expected_names = {"Review.json", *review["files"]}
    if set(names) != expected_names:
        raise ValueError("Unexpected bundle files")
    for relative, digest in review["files"].items():
        if sha(destination / relative) != digest:
            raise ValueError("Reviewed input changed: " + relative)
    if review["all_plan6_video_checks_passed"] is not True or review["independent_article_review"] is not True:
        raise ValueError("Unready film")
    if review["native_human_review_claimed"] is not False:
        raise ValueError("Unexpected review claim")
    return review


def obtain(config, row, temp, local_bundles=None):
    archive = temp / row["asset_name"]
    if local_bundles:
        shutil.copyfile(local_bundles / row["asset_name"], archive)
    else:
        endpoint = f'repos/{config["repository"]}/releases/assets/{int(row["asset_id"])}'
        with archive.open("wb") as f:
            subprocess.run(["gh", "api", "-H", "Accept: application/octet-stream", endpoint],
                           stdout=f, check=True)
    destination = temp / archive.stem
    destination.mkdir()
    review = unpack(archive, destination, row["sha256"])
    if review["publish_at"] != row["publish_at"]:
        raise ValueError("Bundle date differs from saved online schedule")
    return destination, review


def prepare(site, folder, review, stamp, record):
    slug = review["slug"]
    if (site / f"writing/{slug}.html").exists():
        raise ValueError("Film family already exists; never overwrite")
    before = inventory(site)
    spec = importlib.util.spec_from_file_location("reviewed_film_renderer", folder / "render_film_companion.py")
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    media = {k: str(folder / v) for k, v in review["media"].items() if k != "duration_seconds"}
    media["duration_seconds"] = review["media"]["duration_seconds"]
    renderer.render(site, folder, {"slug": slug, "media": media, "live_root": str(ROOT)}, stamp)
    for name in ["enrich_metadata", "build_author_boxes", "build_analytics", "follow_blocks",
                 "build_feed", "build_llms", "build_ask_index", "build_status_pages"]:
        run(["python3", "-B", f"scripts/{name}.py"], site)
    after = inventory(site)
    changed = sorted(p for p in after if before.get(p) != after[p])
    receipt = record / "Release-Prepared.json"
    write(receipt, {"status": "prepared-locally-not-published", "slug": slug,
                    "automatic_daily_exception": True, "publicationStamp": stamp,
                    "baseHead": run(["git", "rev-parse", "HEAD"], site),
                    "changed": changed, "ownedHashes": {p: after[p] for p in changed},
                    "committed": False, "pushed": False, "liveVerified": False})
    run(["python3", "-B", "scripts/sync_daily_article_hubs.py", "--family-plan", str(folder / "Family-Plan.json"),
         "--release-receipt", str(receipt), "--record-dir", str(record / "Hub-Sync"), "--apply"], site)
    for name in ["follow_blocks", "build_llms"]:
        run(["python3", "-B", f"scripts/{name}.py"], site)
    run(["python3", "-B", "scripts/check_new_article_titles.py", "--release-receipt", str(receipt)], site)
    after = inventory(site)
    changed = sorted(p for p in after if before.get(p) != after[p])
    if set(before) - set(after) or set(changed) - set(review["public_allowlist"]):
        raise ValueError("Changes outside reviewed publication paths")
    return changed


def checks(site):
    commands = [["python3", "-B", f"scripts/{name}.py", "--check"] for name in
                ["build_feed", "build_llms", "enrich_metadata", "build_author_boxes", "build_analytics",
                 "build_press", "build_topic_hubs", "build_article_hubs", "build_ask_index", "build_status_pages",
                 "follow_blocks", "build_brand_layer", "enrich_study_metadata", "build_calculator_embeds",
                 "build_rent_study_locales", "build_profile_facts"]]
    commands += [["python3", "-B", f"scripts/{name}.py"] for name in
                 ["check_locale_parity", "check_internal_links", "test_check_internal_links", "test_notify_indexnow"]]
    commands += [["node", *args] for args in [["scripts/check_guide_locales.mjs"],
                 ["--check", "studies/rent-own-2026/study-ui-localized.mjs"], ["scripts/test_rent_study_locales.mjs"],
                 ["scripts/test_valuation_range.cjs"], ["--check", "js/valuation-range-ui.js"],
                 ["scripts/test_dubai_yield.cjs"], ["--check", "js/dubai-yield-ui.js"]]]
    commands += [["python3", "-B", "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py"]]
    for command in commands:
        run(command, site)
    return len(commands)


def normalize_served_html(data):
    # Cloudflare rewrites public mailto links and adds its email decoder.
    # Decode only this known edge transformation; all other bytes must still match.
    def decode(match):
        encoded = bytes.fromhex(match.group(1).decode("ascii"))
        if len(encoded) < 2:
            raise ValueError("Invalid Cloudflare email encoding")
        return b"mailto:" + bytes(x ^ encoded[0] for x in encoded[1:])
    data = re.sub(rb"/cdn-cgi/l/email-protection#([0-9a-fA-F]+)", decode, data)
    data = re.sub(rb'<script data-cfasync="false" src="/cdn-cgi/scripts/[0-9a-f]+/cloudflare-static/email-decode.min.js"></script>', b"", data)
    return data


def successful_exact_deployment(deployment, statuses, commit):
    return (deployment.get("sha") == commit
            and deployment.get("environment") == "github-pages"
            and bool(statuses) and statuses[0].get("state") == "success")


def verify_live(config, commit, paths):
    # GITHUB_TOKEN pushes do not start Pages automatically; request its existing branch build explicitly.
    run(["gh", "api", "-X", "POST", f'repos/{config["repository"]}/pages/builds'])
    for _ in range(40):
        builds = json.loads(run(["gh", "api", f'repos/{config["repository"]}/pages/builds?per_page=10']))
        exact = next((b for b in builds if b.get("commit") == commit and b.get("status") == "built"), None)
        if exact:
            break
        # The legacy Pages build record can remain errored after a newer Actions
        # deployment succeeds. Require the actual environment's exact SHA/status.
        deployments = json.loads(run(["gh", "api", f'repos/{config["repository"]}/deployments?sha={commit}&environment=github-pages&per_page=5']))
        deployed = False
        for deployment in deployments:
            statuses = json.loads(run(["gh", "api", f'repos/{config["repository"]}/deployments/{deployment["id"]}/statuses']))
            if successful_exact_deployment(deployment, statuses, commit):
                deployed = True
                break
        if deployed:
            break
        time.sleep(15)
    else:
        raise RuntimeError("No successful Pages build for the exact publication commit")
    failed = []
    for relative in paths:
        if not relative.endswith((".html", ".mp4", ".png", ".vtt")):
            continue
        try:
            req = urllib.request.Request(config["site_url"] + "/" + relative,
                                         headers={"User-Agent": "Ahmadreza-site-release-verifier/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                received = r.read()
            expected = (ROOT / relative).read_bytes()
            if relative.endswith(".html"):
                received = normalize_served_html(received)
            if received != expected:
                failed.append(relative + " (content mismatch)")
        except Exception as error:
            failed.append(relative + " (" + type(error).__name__ + ": " + str(error) + ")")
    if failed:
        raise RuntimeError("Pages built; live byte verification incomplete: " + ", ".join(failed))
    print("Exact Pages deployment and live publication content verified (known Cloudflare email-link transformation normalized).")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true", help="Rehearse privately; never copy or commit future films")
    ap.add_argument("--verify-build", action="store_true", help="Test existing Pages build access, without future content")
    ap.add_argument("--local-bundles", type=Path)
    ap.add_argument("--wait-for-slot", action="store_true", help="Bounded cloud prewarm; never publish early")
    args = ap.parse_args()
    config = read(CONFIG)
    validate_schedule(config)
    if args.verify_build and not args.verify:
        verify_live(config, run(["git", "rev-parse", "HEAD"]), ["index.html"])
        return
    now = datetime.now(ZONE)
    if args.wait_for_slot:
        deadline = time.monotonic() + 3 * 3600
        while next_wait_seconds(config, now):
            seconds = next_wait_seconds(config, now)
            if time.monotonic() + seconds > deadline + 1:
                raise RuntimeError("Bounded prewarm expired")
            print(f"Cloud worker ready; waiting {seconds:.0f}s for reviewed21:00slot", flush=True)
            time.sleep(min(seconds, 60))
            now = datetime.now(ZONE)
        # Another reviewed release can land while the runner waits.
        run(["git", "pull", "--ff-only", "origin", "main"])
        config = read(CONFIG)
        validate_schedule(config)
    rows = config["films"] if args.verify else due_rows(config, now)
    if not rows:
        missed = missed_rows(config, now, ROOT)
        if missed:
            raise RuntimeError("MISSED WEBSITE SLOT: " + ",".join(missed) + "; no automatic backfill")
        print("No film due. No publication or backfill.")
        return
    if run(["git", "status", "--porcelain=v1", "--untracked-files=no"]):
        raise ValueError("Concurrent tracked edits")
    base_head = run(["git", "rev-parse", "HEAD"])
    original = inventory(ROOT)
    with tempfile.TemporaryDirectory(prefix="reviewed-film-") as td:
        temp = Path(td).resolve()
        site = temp / "site"
        shutil.copytree(ROOT, site, ignore=shutil.ignore_patterns("__pycache__", "node_modules", ".DS_Store"))
        changed = set()
        last_review = None
        for row in rows:
            folder, review = obtain(config, row, temp, args.local_bundles)
            existing = ROOT / f'writing/{review["slug"]}.html'
            if existing.exists():
                film = ROOT / f'assets/writing/{review["slug"]}/film.mp4'
                if sha(film) != review["files"][review["media"]["film"]]:
                    raise ValueError("Existing family differs from reviewed film")
                receipt = read(ROOT / ("data/film-publications/" + row["key"] + ".json"))
                if receipt["bundle_sha256"] != row["sha256"] or receipt["slug"] != review["slug"]:
                    raise ValueError("Existing publication receipt differs")
                if args.verify:
                    # Still verify the archive/binding, but do not try to render an existing family.
                    print("Existing family bound to reviewed bundle: " + review["slug"])
                    continue
                verify_live(config, base_head, receipt["public_paths"])
                print("Already published; deployment verified without a duplicate commit.")
                return
            if not args.verify:
                refuse_existing_film_day(ROOT, datetime.fromisoformat(row["publish_at"]))
            record = temp / ("record-" + row["key"])
            record.mkdir()
            changed.update(prepare(site, folder, review, now.isoformat(timespec="seconds"), record))
            last_review = review
        count = checks(site)
        if args.verify:
            if inventory(ROOT) != original:
                raise ValueError("Private rehearsal changed the public checkout")
            print(f"PASS: {len(rows)} reviewed bundles, cumulative private rendering and {count} current site checks. No future content published.")
            if args.verify_build:
                verify_live(config, base_head, ["index.html"])
            return
        if len(rows) != 1 or due_rows(config, datetime.now(ZONE)) != rows:
            raise ValueError("Release window expired; no late/burst publication")
        run(["git", "fetch", "origin", "main"])
        if run(["git", "rev-parse", "origin/main"]) != base_head or inventory(ROOT) != original:
            raise ValueError("Concurrent changes; next online retry will rebase from current main")
        for relative in sorted(changed):
            destination = ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(site / relative, destination)
        receipt_path = "data/film-publications/" + now.strftime("%Y-%m-%d") + ".json"
        write(ROOT / receipt_path, {"scheduled_at": rows[0]["publish_at"], "prepared_at": now.isoformat(timespec="seconds"),
                                    "slug": last_review["slug"], "bundle_sha256": rows[0]["sha256"],
                                    "site_checks_passed": count, "public_paths": sorted(changed)})
        changed.add(receipt_path)
        run(["git", "add", "--", *sorted(changed)])
        run(["git", "diff", "--cached", "--check"])
        staged = set(run(["git", "diff", "--cached", "--name-only"]).splitlines())
        if staged != changed:
            raise ValueError("Unexpected staged paths")
        if due_rows(config, datetime.now(ZONE)) != rows:
            raise ValueError("Release window expired before commit")
        run(["git", "config", "user.name", "github-actions[bot]"])
        run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
        run(["git", "commit", "-m", "Publish reviewed daily film " + now.strftime("%Y-%m-%d")])
        run(["git", "push", "origin", "HEAD:main"])
        commit = run(["git", "rev-parse", "HEAD"])
        verify_live(config, commit, sorted(changed))
        print("Published once at the due slot: " + last_review["slug"])


if __name__ == "__main__":
    main()
