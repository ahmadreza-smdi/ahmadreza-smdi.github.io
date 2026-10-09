#!/usr/bin/env python3
"""Export the existing homepage Ask index as static JSON, without evaluating JavaScript.

Usage:
  python3 build_ask_index.py --repo-root /path/to/website --output /path/to/ask-index.json
  python3 build_ask_index.py --repo-root /path/to/website --output /path/to/ask-index.json --check

The three checked-in homepages are the only content sources. Their layout/translation
generator remains authoritative. This export adds no answers, server, or search endpoint.
--report writes private provenance/check evidence separately from the public JSON.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree

BASE = "https://a-samadi.com/"
EMAIL = "ahmadreza.smdi@gmail.com"
LANGUAGES = ("en", "fa", "ar")
VOID_TAGS = frozenset("area base br col embed hr img input link meta param source track wbr".split())
# ECMAScript's WhiteSpace and LineTerminator characters, rather than Python's broader \s.
JS_SPACE = re.compile(r"[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PLACE_CLASSES = (
    "hero-copy", "venture", "section-heading", "feature", "work-card", "timeline-item",
    "capability", "guide-tile", "writing-item", "contact-copy",
)
EXCLUDED_PARAGRAPH_CLASSES = ("section-label", "card-topline", "topic", "copy-status", "company")
# A deliberate extraction contract with the existing client. Fail on a changed contract
# instead of publishing a plausible but stale interpretation of Ask's index.
RUNTIME_CONTRACT = (
    "const dialog = $('dialog.command');",
    "const commands = $$('.command-item', dialog).filter((item) => !item.hasAttribute('data-answer-go'));",
    "const clean = (node) => node.textContent.replace(/\\s+/g, ' ').trim();",
    "const places = $$('.hero-copy, .venture, .section-heading, .feature, .work-card, .bio-copy > p, .timeline-item, .capability, .guide-tile, .writing-item, .contact-copy', $('main'));",
    "const section = place.closest('section');",
    "const label = section && section.querySelector('.section-label');",
    "const title = place.matches('p') ? null : place.querySelector('h1, h2, h3, strong');",
    "const paragraphs = place.matches('p') ? [place] : $$('p', place).filter((p) => !p.matches('.section-label, .card-topline, .topic, .copy-status, .company') && clean(p).length > 24);",
)


class InvalidSource(ValueError):
    """The public sources no longer satisfy this export's contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidSource(message)


def clean_text(value: str) -> str:
    # textContent contributes no separator for <br> or <wbr>. Preserve that behavior.
    return JS_SPACE.sub(" ", value).strip(" ")


def js_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str | None]
    parent: Node | None = field(default=None, repr=False)
    children: list[Node | str] = field(default_factory=list, repr=False)

    def descendants(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.descendants()

    def text(self) -> str:
        return "".join(child.text() if isinstance(child, Node) else child for child in self.children)

    def clean(self) -> str:
        return clean_text(self.text())

    def has_class(self, name: str) -> bool:
        return name in (self.attrs.get("class") or "").split()

    def closest(self, tag: str) -> Node | None:
        current = self
        while current:
            if current.tag == tag:
                return current
            current = current.parent
        return None


class Document(HTMLParser):
    def __init__(self, content: str, source: str):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.tree = Node("document", {})
        self.stack = [self.tree]
        self.feed(content)
        self.close()
        require(len(self.stack) == 1, f"{source}: unclosed HTML element")
        self.nodes = list(self.tree.descendants())
        self.ids: set[str] = set()
        for node in self.nodes:
            identifier = node.attrs.get("id")
            if identifier:
                require(identifier not in self.ids, f"{source}: duplicate ID {identifier}")
                self.ids.add(identifier)

    def handle_starttag(self, tag: str, attributes):
        node = Node(tag, dict(attributes), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attributes):
        node = Node(tag, dict(attributes), self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str):
        require(len(self.stack) > 1 and self.stack[-1].tag == tag,
                f"{self.source}: unsupported/mismatched closing tag {tag}")
        self.stack.pop()

    def handle_data(self, value: str):
        self.stack[-1].children.append(value)


class Exporter:
    def __init__(self, repo_root: Path):
        self.root = repo_root.resolve()
        require(self.root.is_dir(), f"Website root does not exist: {self.root}")
        self.inputs: dict[Path, tuple[bytes, str]] = {}
        self.documents: dict[Path, Document] = {}
        self.internal_destinations: set[str] = set()
        self.external_destinations: set[str] = set()
        self.public_pages: set[str] = set()
        self.contract_hash = hashlib.sha256("\n".join(RUNTIME_CONTRACT).encode()).hexdigest()

    def read(self, path: Path, purpose: str) -> str:
        path = path.resolve()
        require(path.is_relative_to(self.root), f"Source escapes website root: {path}")
        if path not in self.inputs:
            require(path.is_file(), f"Missing source/destination: {path.relative_to(self.root)}")
            self.inputs[path] = (path.read_bytes(), purpose)
        return self.inputs[path][0].decode("utf-8")

    def document(self, path: Path, purpose: str = "link destination") -> Document:
        path = path.resolve()
        if path not in self.documents:
            self.documents[path] = Document(self.read(path, purpose), str(path.relative_to(self.root)))
        return self.documents[path]

    def ensure_unchanged(self):
        for path, (content, _) in self.inputs.items():
            require(path.is_file() and path.read_bytes() == content,
                    f"Source changed while preparing the export: {path.relative_to(self.root)}")

    def check_runtime_contract(self):
        source = self.read(self.root / "js/future.js", "Ask extraction contract")
        for fragment in RUNTIME_CONTRACT:
            require(source.count(fragment) == 1,
                    "Ask extraction contract changed: review js/future.js before regenerating ("
                    + fragment[:72] + ")")

    def load_public_routes(self):
        tree = ElementTree.fromstring(self.read(self.root / "sitemap.xml", "public canonical route allowlist"))
        namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        require(tree.tag == namespace + "urlset", "Unexpected sitemap namespace/shape")
        routes = [node.text.strip() for node in tree.findall(namespace + "url/" + namespace + "loc")
                  if node.text]
        require(routes and len(routes) == len(set(routes)), "Missing/duplicate canonical sitemap routes")
        require(all(url.startswith(BASE) for url in routes), "Unexpected off-site canonical sitemap route")
        self.public_pages = set(routes)

    def check_url(self, url: str) -> None:
        parsed = urlsplit(url)
        require(not parsed.username and not parsed.password, "Credential-bearing URL in public source")
        if parsed.scheme == "mailto":
            require(url == "mailto:" + EMAIL, f"Unexpected personal contact destination: {url}")
            return
        require(parsed.scheme in ("https", "http") and bool(parsed.netloc), f"Unsupported public URL: {url}")
        if parsed.netloc not in ("a-samadi.com", "www.a-samadi.com"):
            self.external_destinations.add(url)
            return  # Existing external destinations are copied, not asserted live/verified.
        require(parsed.scheme == "https", f"Non-HTTPS same-site URL: {url}")
        decoded = unquote(parsed.path)
        require("\\" not in decoded and "\x00" not in decoded, f"Invalid same-site URL path: {url}")
        target = self.root / decoded.lstrip("/")
        if not decoded or decoded.endswith("/"):
            target /= "index.html"
        target = target.resolve()
        require(target.is_relative_to(self.root), f"Same-site destination escapes website root: {url}")
        require(target.suffix == ".html", f"Directory scope requires a public HTML destination: {url}")
        relative = target.relative_to(self.root).as_posix()
        canonical = BASE + (relative.removesuffix("index.html") if target.name == "index.html" else relative)
        require(canonical in self.public_pages, f"Destination is outside the canonical public sitemap: {url}")
        destination = self.document(target)
        canonicals = [node.attrs.get("href") for node in destination.nodes
                      if node.tag == "link" and node.attrs.get("rel") == "canonical"]
        require(canonicals == [canonical], f"Destination does not match its public canonical: {url}")
        robots = [node.attrs.get("content") or "" for node in destination.nodes
                  if node.tag == "meta" and node.attrs.get("name") == "robots"]
        require(not any("noindex" in re.split(r"[,\s]+", directive.lower()) for directive in robots),
                f"Destination is marked noindex: {url}")
        if parsed.fragment:
            require(unquote(parsed.fragment) in destination.ids, f"Missing same-site fragment: {url}")
        self.internal_destinations.add(url)

    def links(self, node: Node, source_url: str) -> list[dict[str, str]]:
        result = []
        for candidate in (node, *node.descendants()):
            href = candidate.attrs.get("href")
            if candidate.tag == "a" and href:
                url = urljoin(source_url, href)
                self.check_url(url)
                result.append({"label": candidate.clean(), "url": url})
        return result

    def locale(self, language: str) -> dict:
        relative = Path("index.html" if language == "en" else language + "/index.html")
        source_url = BASE if language == "en" else BASE + language + "/"
        document = self.document(self.root / relative, "public homepage")
        html_nodes = [node for node in document.nodes if node.tag == "html"]
        require(len(html_nodes) == 1 and html_nodes[0].attrs.get("lang") == language,
                f"{relative}: wrong/missing homepage language")
        if language != "en":
            require(html_nodes[0].attrs.get("dir") == "rtl", f"{relative}: missing RTL direction")
        canonicals = [node.attrs.get("href") for node in document.nodes
                      if node.tag == "link" and node.attrs.get("rel") == "canonical"]
        require(canonicals == [source_url], f"{relative}: unexpected canonical homepage")
        mains = [node for node in document.nodes if node.tag == "main"]
        dialogs = [node for node in document.nodes if node.tag == "dialog" and node.has_class("command")]
        require(len(mains) == 1 and len(dialogs) == 1, f"{relative}: missing/duplicate main or Ask dialog")
        places = [node for node in mains[0].descendants()
                  if any(node.has_class(name) for name in PLACE_CLASSES)
                  or (node.tag == "p" and node.parent and node.parent.has_class("bio-copy"))]
        require(bool(places), f"{relative}: no indexed passages")
        passages = []
        for position, place in enumerate(places, 1):
            section = place.closest("section")
            require(section is not None, f"{relative}: indexed passage outside a section")
            label = next((node for node in section.descendants() if node.has_class("section-label")), None)
            title = None if place.tag == "p" else next(
                (node for node in place.descendants() if node.tag in ("h1", "h2", "h3", "strong")), None)
            paragraphs = [place] if place.tag == "p" else [
                node for node in place.descendants()
                if node.tag == "p" and not any(node.has_class(name) for name in EXCLUDED_PARAGRAPH_CLASSES)
                and js_length(node.clean()) > 24
            ]
            section_id = section.attrs.get("id")
            section_url = urljoin(source_url, "#" + section_id) if section_id else None
            if section_url:
                self.check_url(section_url)
            passage = {
                "position": position,
                "section": label.clean() if label else section.attrs.get("aria-label") or "",
                "title": title.clean() if title else "",
                "text": place.clean(),
                "paragraphs": [node.clean() for node in paragraphs],
                "source_url": source_url,
                "section_url": section_url,
                "links": self.links(place, source_url),
            }
            require(bool(passage["text"]), f"{relative}: empty indexed passage")
            passages.append(passage)
        shortcuts = []
        for node in dialogs[0].descendants():
            if node.tag == "a" and node.has_class("command-item") and "data-answer-go" not in node.attrs:
                require(bool(node.attrs.get("href")), f"{relative}: link shortcut lacks href")
                require(node.attrs.get("data-unavailable") != "true", f"{relative}: unavailable shortcut needs review")
                shortcuts.extend(self.links(node, source_url))
        require(bool(shortcuts), f"{relative}: no link shortcuts")
        self.check_url(source_url)
        return {"language": language, "source_url": source_url, "passages": passages, "shortcuts": shortcuts}

    def build(self) -> dict:
        self.check_runtime_contract()
        self.load_public_routes()
        locales = [self.locale(language) for language in LANGUAGES]
        require(len({len(locale["passages"]) for locale in locales}) == 1,
                "Homepage passage structure differs across languages; regenerate/check locales first")
        require(len({len(locale["shortcuts"]) for locale in locales}) == 1,
                "Homepage link shortcut structure differs across languages")
        data = {"version": 1, "site_url": BASE, "primary_language": "en", "locales": locales}
        encoded = serialize(data)
        emails = set(EMAIL_PATTERN.findall(encoded))
        require(emails == {EMAIL}, f"Unexpected/missing personal email in export: {sorted(emails)}")
        self.ensure_unchanged()
        return data

    def report(self, data: dict, content: bytes, output: Path, mode: str) -> dict:
        try:
            commit = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                                             text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            commit = None
        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "repo_root": str(self.root),
            "base_commit": commit,
            "output": str(output),
            "output_sha256": hashlib.sha256(content).hexdigest(),
            "output_bytes": len(content),
            "runtime_contract_sha256": self.contract_hash,
            "source_files": [{"path": str(path.relative_to(self.root)), "purpose": purpose,
                              "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                             for path, (raw, purpose) in sorted(self.inputs.items())],
            "locales": [{"language": locale["language"], "passages": len(locale["passages"]),
                         "paragraphs": sum(len(passage["paragraphs"]) for passage in locale["passages"]),
                         "shortcuts": len(locale["shortcuts"]),
                         "unanchored_passages": sum(passage["section_url"] is None for passage in locale["passages"])}
                        for locale in data["locales"]],
            "unique_same_site_destinations_checked": len(self.internal_destinations),
            "existing_external_destinations_copied": sorted(self.external_destinations),
            "checks": {"source_provenance": True, "runtime_selectors_and_filters": True,
                       "canonical_languages_and_direction": True, "same_site_files_and_fragments": True,
                       "canonical_public_route_allowlist": True,
                       "personal_contact_only": True, "english_first": True, "source_bytes_unchanged": True},
            "scope": "Static homepage text and existing link directory for consumers that choose to read it; no endpoint or ranking claim.",
        }


def serialize(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_if_unchanged(path: Path, content: bytes, before: bytes | None, exporter: Exporter) -> None:
    require(path not in exporter.inputs, "Output path would overwrite a source")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name + ".", suffix=".tmp", delete=False) as stream:
            temp_path = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        exporter.ensure_unchanged()
        current = path.read_bytes() if path.is_file() else None
        require(current == before, f"Output changed concurrently: {path}")
        os.replace(temp_path, path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, help="Website source directory; defaults to the installed script's parent.parent")
    parser.add_argument("--output", type=Path, help="Static JSON destination; defaults to <repo-root>/ask-index.json")
    parser.add_argument("--check", action="store_true", help="Keep public source/output read-only; fail on missing or stale output")
    parser.add_argument("--report", type=Path, help="Separate PRIVATE provenance/validation report")
    args = parser.parse_args()
    try:
        repo_root = (args.repo_root or Path(__file__).resolve().parent.parent).resolve()
        output = (args.output or repo_root / "ask-index.json").resolve()
        report_path = args.report.resolve() if args.report else None
        if report_path:
            require(not report_path.is_relative_to(repo_root),
                    "Private report must be outside the website root")
            require(report_path != output, "Private report path would overwrite public output")
        before = output.read_bytes() if output.is_file() else None
        exporter = Exporter(repo_root)
        data = exporter.build()
        content = serialize(data).encode("utf-8")
        require(output not in exporter.inputs, "Output path would overwrite a source")
        if args.check:
            require(before is not None, f"Missing static index: {output}")
            try:
                saved = json.loads(before)
            except (ValueError, UnicodeDecodeError) as error:
                raise InvalidSource(f"Invalid static index JSON: {output}") from error
            require(saved == data and before == content,
                    f"Static index differs from the exact current public source: {output}")
            exporter.ensure_unchanged()
            require(output.read_bytes() == before, f"Output changed while checking: {output}")
        elif before != content:
            write_if_unchanged(output, content, before, exporter)
        if report_path:
            # Evidence is always separate; it is not a field in the public export.
            report_before = report_path.read_bytes() if report_path.is_file() else None
            report = serialize(exporter.report(data, content, output, "check" if args.check else "generate")).encode("utf-8")
            write_if_unchanged(report_path, report, report_before, exporter)
        counts = ", ".join(f"{locale['language']}: {len(locale['passages'])} passages/{len(locale['shortcuts'])} link shortcuts"
                           for locale in data["locales"])
        print(f"PASS static Ask index ({counts}); source text, routes and contract validated")
        return 0
    except (InvalidSource, OSError, UnicodeError, ElementTree.ParseError) as error:
        print(f"FAIL static Ask index: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
