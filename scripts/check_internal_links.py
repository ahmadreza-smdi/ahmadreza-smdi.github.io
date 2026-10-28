"""Check crawlable same-site links and fragments in the published HTML tree."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from xml.etree import ElementTree
import argparse


SITE = "https://a-samadi.com/"
HOSTS = {"a-samadi.com", "www.a-samadi.com"}


class PageLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.noindex = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag == "meta" and values.get("name", "").lower() == "robots":
            self.noindex = "noindex" in values.get("content", "").lower()


def audit(root: Path, check_orphans: bool = False) -> tuple[int, int, list[str]]:
    root = root.resolve()
    pages: dict[Path, PageLinks] = {}
    for path in sorted(root.rglob("*.html")):
        page = PageLinks()
        page.feed(path.read_text(encoding="utf-8"))
        pages[path.resolve()] = page

    checked = 0
    problems: list[str] = []
    inbound: set[Path] = set()
    for source, page in pages.items():
        relative = source.relative_to(root).as_posix()
        route = relative.removesuffix("index.html") if source.name == "index.html" else relative
        for href in page.links:
            target = urlparse(urljoin(SITE + route, href))
            if target.scheme not in {"http", "https"} or target.hostname not in HOSTS:
                continue
            checked += 1
            site_path = unquote(target.path).lstrip("/")
            destination = root / site_path
            if not site_path or site_path.endswith("/"):
                destination /= "index.html"
            destination = destination.resolve()
            if destination != source and not page.noindex:
                inbound.add(destination)
            label = f"{relative}: {href}"
            if not destination.is_relative_to(root) or not destination.is_file():
                problems.append(f"{label} -> missing local file")
            elif target.fragment and destination.suffix == ".html":
                target_page = pages.get(destination)
                if target_page is not None and unquote(target.fragment) not in target_page.ids:
                    problems.append(f"{label} -> missing fragment")
    if check_orphans:
        # Opt in for maintenance: frozen daily publishers do not emit watch-page backlinks.
        # A self link or an embedded/noindex helper is not a discovery path.
        namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        for node in ElementTree.parse(root / "sitemap.xml").getroot().findall(namespace + "url"):
            url = node.findtext(namespace + "loc")
            relative = unquote(urlparse(url).path).lstrip("/")
            destination = (root / (relative + "index.html" if not relative or relative.endswith("/") else relative)).resolve()
            if destination in pages and not pages[destination].noindex and destination not in inbound:
                problems.append(f"{relative or '/'} -> indexable sitemap URL has no inbound <a> link")
    return len(pages), checked, problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-orphans", action="store_true", help="Also require inbound links for indexable sitemap pages")
    args = parser.parse_args()
    count, checked, problems = audit(Path(__file__).resolve().parent.parent, args.check_orphans)
    for problem in problems:
        print(problem)
    if problems:
        raise SystemExit(f"FAIL: {len(problems)} broken internal links across {count} HTML pages")
    print(f"PASS: {checked} internal links across {count} HTML pages; no missing files or fragments")
