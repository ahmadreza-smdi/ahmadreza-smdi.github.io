"""Manual read-only release check. Requires --live; public requests are serialized and anonymous."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import build_opener, Request, HTTPRedirectHandler

from seo_document import SITE
from check_internal_links import protected
from site_resources import inventory

ROOT = Path(__file__).resolve().parents[1]


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class Reader:
    def __init__(self, interval=1.12):
        self.next = 0.0
        self.interval = max(1.0, interval)
        self.opener = build_opener(NoRedirects())

    def get(self, url, byte_range=False):
        if (
            urlsplit(url).hostname != urlsplit(SITE).hostname
            or urlsplit(url).scheme != "https"
        ):
            raise ValueError("Only the public website is permitted")
        time.sleep(max(0, self.next - time.monotonic()))
        self.next = time.monotonic() + self.interval
        headers = {"User-Agent": "Website-Review/1.0", "Accept-Encoding": "identity"}
        if byte_range:
            headers["Range"] = "bytes=0-4095"
        req = Request(url, headers=headers)
        try:
            with self.opener.open(req, timeout=25) as response:
                data = response.read(4096) if byte_range else response.read()
                headers = dict(response.headers.items())
                if (
                    byte_range
                    and response.status == 200
                    and response.headers.get("Content-Length") is None
                ):
                    total = len(data)
                    while chunk := response.read(128 * 1024):
                        total += len(chunk)
                    headers["Content-Length"] = str(total)
                return response.status, headers, data
        except HTTPError as exc:
            code = exc.code
            exc.close()
            return code, {}, b""


def excluded_files(root):
    # This repository's _config.yml uses a simple explicit block list. Refuse patterns or aliases.
    paths = []
    in_list = False
    for line in (root / "_config.yml").read_text().splitlines():
        if line == "exclude:":
            in_list = True
            continue
        if in_list and not line.strip():
            continue
        if in_list and line.lstrip().startswith("#"):
            continue
        if in_list and not line.startswith(" "):
            in_list = False
        if not in_list:
            continue
        m = re.fullmatch(r"  - ([A-Za-z0-9._/-]+)", line)
        if not m:
            raise ValueError("Unrecognized Pages exclusion; review the literal paths")
        rel = m[1].rstrip("/")
        p = root / rel
        if Path(rel).is_absolute() or ".." in Path(rel).parts or protected(rel):
            raise ValueError("Unsafe exclusion")
        if p.is_dir():
            paths.extend(
                q.relative_to(root).as_posix()
                for q in p.rglob("*")
                if q.is_file()
                and not q.is_symlink()
                and not protected(q.relative_to(root))
            )
        else:
            paths.append(rel)
    return sorted(set(paths))


def normalized_html(data):
    # Remove only the site's two documented, non-visible CDN directives; keep every other byte.
    return data.replace(b"<!--email_off-->", b"").replace(b"<!--/email_off-->", b"")


def compare(root, rel, reader, want_absent=False):
    p = root / rel
    if protected(rel) or p.is_symlink():
        raise ValueError("Unapproved public verification path")
    url = SITE + quote(rel, safe="/._-") + "?v=" + secrets.token_hex(6)
    size = p.stat().st_size if p.is_file() else 0
    partial = (
        not want_absent
        and size > 650000
        and p.suffix.lower() not in (".html", ".js", ".mjs", ".css", ".json")
    )
    status, headers, data = reader.get(url, partial)
    if want_absent:
        return dict(
            path=rel, url=url, status=status, mode="excluded", pass_check=status == 404
        )
    with p.open("rb") as fh:
        expected = fh.read(4096) if partial else fh.read()
    same = expected == data
    compare_ok = same or (
        p.suffix == ".html" and normalized_html(expected) == normalized_html(data)
    )
    head = {k.lower(): v for k, v in headers.items()}
    size_ok = not partial or (
        head.get("content-range", "").endswith("/" + str(size))
        if status == 206
        else head.get("content-length") == str(size)
    )
    return dict(
        path=rel,
        url=url,
        status=status,
        mode="first 4096 bytes and total length" if partial else "complete file",
        bytes=len(data),
        expected_bytes=size,
        sha256=sha256(data).hexdigest(),
        reference_sha256=sha256(expected).hexdigest(),
        raw_equal=same,
        pass_check=status in ((200, 206) if partial else (200,))
        and size_ok
        and compare_ok,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if not args.live:
        print("SKIP: public verification requires --live")
        return 0
    pg, resources, refs, missing = inventory(ROOT)
    excluded = excluded_files(ROOT)
    overlap = set(excluded) & resources
    if missing or overlap:
        raise SystemExit(
            f"FAIL local reachability: {len(missing)} broken references, {len(overlap)} exclusions in use"
        )
    findings = []
    reader = Reader()
    checks = [(p, True) for p in excluded] + [(p, False) for p in sorted(resources)]
    for rel, absent in checks:
        try:
            r = compare(ROOT, rel, reader, absent)
        except (OSError, ValueError, URLError) as exc:
            r = dict(path=rel, pass_check=False, error=type(exc).__name__)
        findings.append(r)
        if args.json and (
            len(findings) % 20 == 0
            or not r["pass_check"]
            or len(findings) == len(checks)
        ):
            target = args.json.with_suffix(".partial")
            target.write_text(
                json.dumps(
                    {"records": findings, "finished": len(findings) == len(checks)},
                    indent=2,
                )
                + "\n"
            )
            target.replace(args.json)
        if not r["pass_check"]:
            print("FAIL public route", rel, r.get("status", r.get("error")), flush=True)
    bad = sum(not r["pass_check"] for r in findings)
    print(
        f"{'FAIL' if bad else 'PASS'} live website: {len(pg)} pages, {len(resources) - len(pg)} resources, {len(excluded)} exclusions, {bad} differences"
    )
    return int(bool(bad))


if __name__ == "__main__":
    sys.exit(main())
