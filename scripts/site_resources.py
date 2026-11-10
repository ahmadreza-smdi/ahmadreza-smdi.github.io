"""Inventory referenced public resources, including dependencies resolved by CSS and JavaScript."""

from collections import defaultdict, deque
from pathlib import Path
import json
import re
from urllib.parse import urljoin, urlsplit, unquote
from seo_document import SITE, Document, public_url
from check_internal_links import site_pages as pages, protected

EXT = r"(?:html?|css|js|mjs|woff2?|ttf|png|jpe?g|webp|avif|svg|gif|ico|mp4|webm|vtt|pdf|vcf|zip|json|webmanifest|txt|xml|csv|xlsx|cff)"
LITERAL = re.compile(
    r"""["']((?:https://a-samadi\.com/|/|\.\.?/)?[a-zA-Z0-9_%@./+-]+\."""
    + EXT
    + r"""(?:[?#][^"'\s]*)?)["']""",
    re.I,
)
CSS = re.compile(r'url\(\s*["\x27]?([^)\s"\x27]+)', re.I)
SOURCE = {
    "html",
    "htm",
    "css",
    "js",
    "mjs",
    "webmanifest",
    "json",
    "xml",
    "svg",
    "md",
    "txt",
    "csv",
    "cff",
}


def resolve(origin, ref, allowed_path=None):
    if not ref or ref.startswith(
        ("#", "data:", "blob:", "mailto:", "tel:", "javascript:")
    ):
        return None
    target = urlsplit(urljoin(public_url(origin), ref))
    if target.hostname != urlsplit(SITE).hostname or target.scheme not in (
        "http",
        "https",
    ):
        return None
    path = unquote(target.path).lstrip("/")
    path = (path + "index.html") if not path or path.endswith("/") else path
    if allowed_path is not None and not allowed_path(path):
        raise ValueError(f"{origin} references a forbidden public path: {path}")
    return None if ".." in Path(path).parts or (protected(path) and allowed_path is None) else path


def inventory(root, allowed_path=None):
    root = root.resolve()
    html = {p.relative_to(root).as_posix() for p in pages(root)}
    seen = set()
    references = defaultdict(set)
    missing = set()
    queue = deque(
        sorted(
            html
            | {
                s
                for s in (
                    "robots.txt",
                    "sitemap.xml",
                    "site.webmanifest",
                    "llms.txt",
                    "llms-full.txt",
                    "humans.txt",
                )
                if (root / s).is_file()
            }
        )
    )
    while queue:
        origin = queue.popleft()
        if origin in seen:
            continue
        seen.add(origin)
        p = root / origin
        if (
            p.suffix.lstrip(".").lower() not in SOURCE
            or p.is_symlink()
            or not p.is_file()
        ):
            continue
        raw = p.read_text(encoding="utf-8", errors="replace")
        refs = set()
        if origin in html:
            d = Document(raw)
            for e in d.elements:
                for key in (
                    "href",
                    "src",
                    "poster",
                    "data-src",
                    "data-poster",
                    "data-asset",
                    "action",
                ):
                    if e.get(key):
                        refs.add((e.get(key), True))
                for key in ("srcset", "imagesrcset"):
                    refs.update(
                        (v.strip().split()[0], True)
                        for v in e.get(key).split(",")
                        if v.strip() and not v.startswith("data:")
                    )
                if e.tag == "meta" and (
                    e.get("property") in ("og:image", "og:video")
                    or e.get("name") == "twitter:image"
                ):
                    refs.add((e.get("content"), True))
        if p.suffix in (".css", ".html", ".svg"):
            refs.update((v, True) for v in CSS.findall(raw) if "${" not in v)
        if p.suffix in (".js", ".mjs", ".html"):
            deps = re.findall(
                r"""(?:\bfrom\s+|\bimport\s*\(?\s*|\bfetch\(\s*)["']((?:\.{0,2}/)[^"'\s]+)["']""",
                raw,
            )
            refs.update((v, True) for v in deps)
        if p.suffix == ".webmanifest":
            manifest = json.loads(raw)
            refs.update((item["src"], True) for item in manifest.get("icons", []))
        refs.update((v, False) for v in LITERAL.findall(raw))
        if origin == "robots.txt":
            refs.update(
                (v, True) for v in re.findall(r"^Sitemap:\s*(\S+)", raw, re.M | re.I)
            )
        for ref, explicit in refs:
            dest = resolve(origin, ref, allowed_path if explicit else None)
            if not dest:
                continue
            candidate = root / dest
            if allowed_path and not allowed_path(dest):
                continue
            if candidate.is_file() and not candidate.is_symlink() and candidate.resolve() == candidate:
                references[dest].add(origin)
                if dest not in seen:
                    queue.append(dest)
            elif explicit and not ref.startswith("?"):
                missing.add((origin, dest))
    return html, seen, references, missing
