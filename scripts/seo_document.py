"""Read public HTML without executing scripts. Shared by local checks and manual measurements."""

from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import urljoin

SITE = "https://a-samadi.com/"
VOID = set(
    "area base br col embed hr img input link meta param source track wbr".split()
)


class Element:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []

    def get(self, attr):
        return self.attrs.get(attr) or ""

    def content(self, visible=False):
        if visible and self.tag in ("style", "script", "template"):
            return ""
        return "".join(
            x if isinstance(x, str) else x.content(visible) for x in self.children
        )

    def text(self):
        return " ".join(self.content(True).split())

    def within(self, predicate):
        elem = self
        while elem:
            if predicate(elem):
                return True
            elem = elem.parent
        return False


class Document(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.current = self.root
        self.elements = []
        self.feed(raw)
        self.close()

    def handle_starttag(self, tag, attrs):
        el = Element(tag, attrs, self.current)
        self.current.children.append(el)
        self.elements.append(el)
        if tag not in VOID:
            self.current = el

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        el = self.current
        while el.parent:
            if el.tag == tag:
                self.current = el.parent
                return
            el = el.parent

    def handle_data(self, data):
        self.current.children.append(data)

    def tags(self, tag):
        return [e for e in self.elements if e.tag == tag]

    def meta(self, key):
        return [
            e.get("content")
            for e in self.tags("meta")
            if (e.get("name") or e.get("property")).lower() == key
        ]

    def links(self, rel):
        return [e for e in self.tags("link") if rel in e.get("rel").lower().split()]

    def blocks(self):
        return [
            e.content()
            for e in self.tags("script")
            if e.get("type").lower() == "application/ld+json"
        ]

    def snapshot(self, path):
        titles = [
            e.text() for e in self.tags("title") if e.within(lambda e: e.tag == "head")
        ]
        descriptions = self.meta("description")
        canonicals = [e.get("href") for e in self.links("canonical")]
        return dict(
            path=path,
            title=titles[0] if titles else "",
            description=descriptions[0] if descriptions else "",
            canonical=canonicals[0] if canonicals else "",
            h1=[e.text() for e in self.tags("h1")],
            jsonld_sha256=[
                sha256(s.encode("utf-8")).hexdigest() for s in self.blocks()
            ],
        )

    def indexable(self):
        directives = " ".join(self.meta("robots") + self.meta("googlebot")).lower()
        return not re.search(r"\b(noindex|none)\b", directives)


def public_url(path):
    return urljoin(
        SITE,
        path[:-10] if path.endswith("/index.html") or path == "index.html" else path,
    )


def nodes(value):
    if isinstance(value, dict):
        yield value
        for val in value.values():
            yield from nodes(val)
    elif isinstance(value, list):
        for val in value:
            yield from nodes(val)
