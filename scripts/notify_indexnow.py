#!/usr/bin/env python3
"""Notify IndexNow only about changed, canonical public pages after Pages succeeds."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
HOST = "a-samadi.com"
BASE = f"https://{HOST}"
KEY = "a4ee77f7346407b59908d16f095ac9dd"
KEY_LOCATION = f"{BASE}/{KEY}.txt"
REPOSITORY = "ahmadreza-smdi/ahmadreza-smdi.github.io"
SHA = re.compile(r"^[0-9a-f]{40}$")


def listed_urls():
    root = ElementTree.parse(ROOT / "sitemap.xml").getroot()
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    return {item.text for item in root.findall(f"{namespace}url/{namespace}loc")}


def public_url(path):
    if path == "index.html":
        return BASE + "/"
    if path in {"fa/index.html", "ar/index.html"}:
        return BASE + "/" + path.split("/")[0] + "/"
    return BASE + "/" + path


def changed_urls(before, after, canonical):
    if not SHA.fullmatch(after) or not SHA.fullmatch(before):
        raise ValueError("Expected complete Git commit SHAs")
    if before == "0" * 40:
        command = ["git", "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", after]
    else:
        command = ["git", "diff", "--name-only", "--diff-filter=ACMR", before, after]
    result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    urls = {public_url(path) for path in result.stdout.splitlines() if path.endswith(".html")}
    return sorted(urls & canonical)


def github_json(path, token):
    request = Request(
        f"https://api.github.com/repos/{REPOSITORY}/{path}",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "User-Agent": "ahmadreza-indexnow"},
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def wait_for_pages(sha, token):
    if not token:
        raise ValueError("GITHUB_TOKEN required to verify deployment")
    for attempt in range(30):
        deployments = github_json(f"deployments?sha={sha}&environment=github-pages&per_page=10", token)
        for deployment in deployments:
            if deployment.get("sha") != sha or deployment.get("environment") != "github-pages":
                continue
            statuses = github_json(f"deployments/{deployment['id']}/statuses?per_page=1", token)
            if statuses and statuses[0].get("state") == "success":
                return
            if statuses and statuses[0].get("state") in {"failure", "error"}:
                raise RuntimeError("GitHub Pages deployment failed; no URLs were submitted")
        if attempt < 29:
            time.sleep(10)
    raise RuntimeError("GitHub Pages success was not observed; no URLs were submitted")


def verify_live_key():
    with urlopen(Request(KEY_LOCATION, headers={"User-Agent": "ahmadreza-indexnow"}), timeout=20) as response:
        if response.status != 200 or response.read(256).decode("utf-8").strip() != KEY:
            raise RuntimeError("Live IndexNow key file does not match source")


def submit(urls):
    body = json.dumps({"host": HOST, "key": KEY, "keyLocation": KEY_LOCATION, "urlList": urls}).encode("utf-8")
    request = Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "ahmadreza-indexnow"}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            status = response.status
    except HTTPError as error:
        status = error.code
    if status not in {200, 202}:
        raise RuntimeError(f"IndexNow returned HTTP {status}; no indexing claim is possible")
    print(f"IndexNow received {len(urls)} changed canonical URL(s), HTTP {status}; indexing is not guaranteed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before")
    parser.add_argument("--after")
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--wait-for-pages", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if (ROOT / f"{KEY}.txt").read_text(encoding="utf-8").strip() != KEY:
        raise RuntimeError("Source IndexNow key file does not match notifier")
    if args.url and args.wait_for_pages:
        parser.error("--wait-for-pages requires --before and --after")
    canonical = listed_urls()
    if args.url:
        if args.before or args.after:
            parser.error("Use either --url or --before/--after")
        urls = sorted(set(args.url))
        if any(url not in canonical for url in urls):
            parser.error("Every explicit URL must be in the canonical sitemap")
    else:
        if not args.before or not args.after:
            parser.error("Both --before and --after are required")
        urls = changed_urls(args.before, args.after, canonical)
    if not urls:
        print("No changed canonical HTML pages; no IndexNow submission")
        return
    if args.dry_run:
        print("Would submit:\n" + "\n".join(urls))
        return
    if args.wait_for_pages:
        wait_for_pages(args.after, os.environ.get("GITHUB_TOKEN"))
    verify_live_key()
    submit(urls)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, HTTPError, URLError) as error:
        print(f"IndexNow notification stopped: {error}", file=sys.stderr)
        sys.exit(1)
