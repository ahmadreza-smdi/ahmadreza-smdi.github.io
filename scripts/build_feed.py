"""Build or check the English RSS feed from existing Article metadata."""

import argparse
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
import json
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://a-samadi.com/"
FEED_URL = BASE + "writing/feed.xml"
ATOM = "http://www.w3.org/2005/Atom"
DC = "http://purl.org/dc/elements/1.1/"
ET.register_namespace("atom", ATOM)
ET.register_namespace("dc", DC)


class PageMetadata(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.language = None
        self.canonicals = []
        self.feed_links = []
        self.records = []
        self.json_buffer = None
        self.feed(path.read_text())

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "html":
            self.language = attrs.get("lang")
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonicals.append(attrs.get("href"))
        if (tag == "link" and attrs.get("rel") == "alternate"
                and attrs.get("type") == "application/rss+xml"):
            self.feed_links.append(attrs.get("href"))
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.json_buffer = ""

    def handle_data(self, data):
        if self.json_buffer is not None:
            self.json_buffer += data

    def handle_endtag(self, tag):
        if tag == "script" and self.json_buffer is not None:
            schema = json.loads(self.json_buffer)
            self.records.extend(schema.get("@graph", [schema]))
            self.json_buffer = None

    def record(self, kind, canonical):
        records = [item for item in self.records if item.get("@type") == kind]
        if (self.language != "en" or self.canonicals != [canonical]
                or self.feed_links != [FEED_URL] or len(records) != 1):
            raise ValueError(f"Invalid English metadata or RSS discovery link: {canonical}")
        record = records[0]
        if record.get("url") != canonical or record.get("inLanguage") != "en":
            raise ValueError(f"Inconsistent structured-data URL or language: {canonical}")
        return record


def publication_time(value):
    # RSS requires a time. Date-only source values use midnight UTC without
    # claiming a more precise publication time than the source provides.
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), time(), timezone.utc)
    published = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if published.tzinfo is None:
        raise ValueError(f"Publication datetime needs a timezone: {value}")
    return published.astimezone(timezone.utc)


def build_feed():
    hub = PageMetadata(ROOT / "writing/index.html").record(
        "CollectionPage", BASE + "writing/"
    )
    articles = []
    for path in sorted((ROOT / "writing").glob("*.html")):
        if path.name == "index.html":
            continue
        canonical = BASE + "writing/" + path.name
        article = PageMetadata(path).record("Article", canonical)
        for field in ("headline", "description", "datePublished"):
            if not isinstance(article.get(field), str) or not article[field].strip():
                raise ValueError(f"Missing {field}: {canonical}")
        if article.get("author") != hub.get("author"):
            raise ValueError(f"Inconsistent existing author: {canonical}")
        articles.append((publication_time(article["datePublished"]), article))
    if not articles:
        raise ValueError("No English articles found")
    articles.sort(key=lambda item: (-item[0].timestamp(), item[1]["url"]))

    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    for tag, value in (
        ("title", hub["name"]),
        ("link", hub["url"]),
        ("description", hub["description"]),
        ("language", "en"),
        (f"{{{DC}}}creator", hub["author"]["name"]),
    ):
        ET.SubElement(channel, tag).text = value
    ET.SubElement(channel, f"{{{ATOM}}}link", {
        "href": FEED_URL, "rel": "self", "type": "application/rss+xml"
    })
    for published, article in articles:
        item = ET.SubElement(channel, "item")
        for tag, value in (
            ("title", article["headline"]),
            ("link", article["url"]),
            ("description", article["description"]),
            (f"{{{DC}}}creator", article["author"]["name"]),
            ("pubDate", format_datetime(published, usegmt=True)),
        ):
            ET.SubElement(item, tag).text = value
        ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = article["url"]
    ET.indent(rss, space="  ")
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True) + b"\n", len(articles)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the saved feed is stale")
    args = parser.parse_args()
    content, count = build_feed()
    target = ROOT / "writing/feed.xml"
    if args.check:
        if not target.is_file() or target.read_bytes() != content:
            raise SystemExit("RSS feed is missing or stale; run python3 scripts/build_feed.py")
        print(f"PASS RSS: {count} English articles, source metadata and discovery links match")
    else:
        target.write_bytes(content)
        print(f"Built writing/feed.xml with {count} English articles")


if __name__ == "__main__":
    main()
