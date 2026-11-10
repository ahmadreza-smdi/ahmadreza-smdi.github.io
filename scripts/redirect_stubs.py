"""Validate structural redirect stubs before exempting them from indexable-page checks."""
import re
from urllib.parse import unquote, urljoin, urlsplit
from seo_document import Document, SITE, public_url
from check_internal_links import protected


def locale(path):
    prefix = path.split("/", 1)[0]
    return prefix if prefix in {"ar", "fa"} else "en"


def inspect(root, path, doc):
    """Return None for ordinary pages or a list of errors for an explicitly marked stub."""
    html = doc.tags("html")
    if not html or "redirect-stub" not in html[0].get("class").split():
        if any(e.get("http-equiv").lower() == "refresh" for e in doc.tags("meta")):
            return ["redirect requires an explicitly marked stub"]
        return None
    errors = []
    url = public_url(path)
    refresh = [e.get("content") for e in doc.tags("meta") if e.get("http-equiv").lower() == "refresh"]
    match = re.fullmatch(r"\s*0\s*;\s*url\s*=\s*(\S+)\s*", refresh[0], re.I) if len(refresh) == 1 else None
    if not match:
        return ["expected one immediate refresh with an explicit URL"]
    to = urljoin(url, match[1])
    split = urlsplit(to)
    if not to.startswith(SITE) or split.query or split.fragment or to == url:
        return ["target must be a different canonical URL on the same site"]
    canon = [e.get("href") for e in doc.links("canonical")]
    links = doc.tags("a")
    if canon != [to] or len(links) != 1 or urljoin(url, links[0].get("href")) != to or not links[0].text():
        errors.append("canonical and one visible link must match the refresh target")
    if not doc.indexable():
        errors.append("stub includes noindex")
    rel = unquote(split.path).lstrip("/")
    if not rel or rel.endswith("/"):
        rel += "index.html"
    target = root / rel
    if protected(rel) or not target.resolve().is_relative_to(root.resolve()) or not target.is_file() or target.is_symlink():
        return errors + ["target is missing or unsafe"]
    dest = Document(target.read_text(encoding="utf-8"))
    tags = dest.tags("html")
    if locale(path) != locale(rel) or html[0].get("lang").split("-")[0] != locale(path) or not tags or tags[0].get("lang").split("-")[0] != locale(path):
        errors.append("target and stub must have the same language")
    if not dest.indexable() or any(e.get("http-equiv").lower() == "refresh" for e in dest.tags("meta")):
        errors.append("target must be an indexable final page")
    if [e.get("href") for e in dest.links("canonical")] != [to]:
        errors.append("target is not self-canonical")
    return errors
