"""Validate public video players, VideoObjects and discovery entries without sending requests."""
from pathlib import Path
import json
import re
from urllib.parse import urljoin, urlsplit, unquote
from xml.etree import ElementTree
from check_internal_links import protected, site_pages
from enrich_metadata import local_image_dimensions, video_nodes, video_datetime_issues
from seo_document import Document, SITE, public_url, nodes

ROOT = Path(__file__).resolve().parents[1]
DURATION = re.compile(r"PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?")


def reachable(root, url):
    if not isinstance(url, str) or not url.startswith(SITE):
        return False
    path = unquote(urlsplit(url).path).lstrip("/")
    file = root / path
    return not protected(path) and file.resolve().is_relative_to(root.resolve()) and file.is_file() and not file.is_symlink()


def film_issues(root, film):
    issues = []
    for field in ("name", "description"):
        if not isinstance(film.get(field), str) or not film[field].strip():
            issues.append(f"missing {field}")
    thumbnail = film.get("thumbnailUrl")
    thumbnails = thumbnail if isinstance(thumbnail, list) else [thumbnail]
    if not thumbnails or not all(reachable(root, u) for u in thumbnails):
        issues.append("missing or unreadable thumbnailUrl")
    content, embed = film.get("contentUrl"), film.get("embedUrl")
    if not (content or embed) or any(not reachable(root, u) for u in (content, embed) if u):
        issues.append("missing or unreadable contentUrl/embedUrl")
    when = film.get("uploadDate") or ""
    if not isinstance(when, str) or not when.endswith("+03:30") or video_datetime_issues(when):
        issues.append("invalid uploadDate or publishing offset")
    value = film.get("duration")
    match = DURATION.fullmatch(value) if isinstance(value, str) else None
    if not match or not any(float(v) > 0 for v in match.groups() if v):
        issues.append("missing or invalid duration")
    return issues


def image_issues(doc, graph, url, dimensions):
    images = {n.get("contentUrl"): n for n in graph if n.get("@type") == "ImageObject"}
    errors = []
    for tag in doc.tags("img"):
        src = urljoin(url, tag.get("src"))
        if not tag.get("alt") or not src.startswith((SITE+"assets/writing/", SITE+"assets/carousels/",
                                                     SITE+"assets/img/", SITE+"studies/rent-burden/")):
            continue
        annotation = images.get(src)
        size = dimensions(src)
        if not annotation or not size or (annotation.get("width"), annotation.get("height")) != size:
            errors.append(f"editorial image lacks accurate dimensions or contentUrl: {src}")
    return errors


def inspect(root):
    records = []
    sitemap = ElementTree.parse(root / "sitemap.xml")
    entries = {entry.findtext("{*}loc"): entry.findall("{*}video") for entry in sitemap.findall("{*}url")}
    by_content = {}
    for location, films in entries.items():
        for film in films:
            by_content.setdefault(film.findtext("{*}content_loc"), set()).add(location)
    for file in site_pages(root):
        rel = file.relative_to(root).as_posix()
        raw = file.read_text(encoding="utf-8")
        doc = Document(raw)
        players = doc.tags("video")
        films = list(video_nodes(raw))
        url = public_url(rel)
        graph = [n for block in doc.blocks() for n in nodes(json.loads(block))]
        if doc.indexable():
            image_errors = image_issues(doc, graph, url, local_image_dimensions)
            if image_errors:
                records.append((rel, "", image_errors))
        if not (players or films or rel.startswith("watch/")):
            continue
        watch = rel.startswith("watch/") and not rel.startswith("watch/embed/")
        playable = {urljoin(url, e.get("src")) for e in players + doc.tags("source")
                    if e.get("src") and e.within(lambda parent: parent.tag == "video")}
        if (players or watch) and doc.indexable() and not films:
            records.append((rel, "", ["indexable player lacks VideoObject"]))
        for film in films:
            issues = film_issues(root, film)
            content = film.get("contentUrl")
            if players and content and content not in playable:
                issues.append("structured content differs from visible player")
            if content and not by_content.get(content):
                issues.append("film absent from video sitemap")
            if watch:
                if not players or not film.get("@id") or not any(
                    n.get("@type") == "WebPage" and n.get("mainEntity") == {"@id": film["@id"]} for n in graph
                ):
                    issues.append("watch page does not identify its visible film as the main content")
                if url not in by_content.get(content, set()):
                    issues.append("watch page absent from video sitemap")
            for entry in entries.get(url, []):
                if entry.findtext("{*}content_loc") == content and (
                    entry.findtext("{*}thumbnail_loc") != film.get("thumbnailUrl")
                    or entry.findtext("{*}publication_date") != film.get("uploadDate")
                ):
                    issues.append("video sitemap thumbnail or publication date differs")
            records.append((rel, content or film.get("embedUrl", ""), issues))
    return records


if __name__ == "__main__":
    checks = inspect(ROOT)
    bad = [(p, error) for p, _, issues in checks for error in issues]
    for path, error in bad:
        print(f"{path}: {error}")
    print(f"{'FAIL' if bad else 'PASS'}: {len(checks)} page/film annotations; {len(bad)} issues")
    raise SystemExit(bool(bad))
