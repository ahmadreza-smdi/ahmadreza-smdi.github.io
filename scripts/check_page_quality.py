"""Offline checks for locale reachability, alternate destinations and initial asset budgets."""
from collections import deque
from functools import lru_cache
from pathlib import Path
import re
import sys

from check_internal_links import site_pages
from seo_document import Document, public_url
from site_resources import CSS, resolve

ROOT = Path(__file__).resolve().parents[1]
# Uncompressed first-party resources declared for the page before scrolling.
# Measured separately from optional video playback or interactive downloads.
INITIAL_BYTE_LIMIT = 512 * 1024
EXPLORER_BYTE_LIMIT = 1792 * 1024
APPROVED_ARABIC_NAME = "أحمدرضا صمدي"


def language(path):
    prefix = path.split("/", 1)[0]
    return prefix if prefix in ("fa", "ar") else "en"


def eligible(file, root):
    return file.is_file() and file.resolve().is_relative_to(root.resolve()) and not file.is_symlink()


@lru_cache(maxsize=128)
def css_dependencies(file, origin):
    return tuple(filter(None, (resolve(origin, ref) for ref in CSS.findall(file.read_text()))))


def page_weight(root, path, doc):
    resources = {path}
    for el in doc.elements:
        ref = ""
        if el.tag == "script":
            ref = el.get("src")
        elif el.tag == "link" and set(el.get("rel").lower().split()) & {"preload", "stylesheet"}:
            ref = el.get("href")
        elif el.tag == "img" and el.get("loading").lower() != "lazy":
            candidates = [resolve(path, item.strip().split()[0]) for item in el.get("srcset").split(",") if item.strip()]
            files = [asset for asset in candidates if asset and eligible(root / asset, root)]
            if files:
                resources.add(max(files, key=lambda asset: (root / asset).stat().st_size))
                continue
            ref = el.get("src")
        elif el.tag == "video":
            ref = el.get("poster")
        if ref:
            dest = resolve(path, ref)
            if dest:
                resources.add(dest)
    for asset in tuple(resources):
        file = root / asset
        if file.suffix == ".css" and eligible(file, root):
            resources.update(css_dependencies(file, asset))
    return sum((root / asset).stat().st_size for asset in resources if eligible(root / asset, root))


def persian_typography(doc):
    problems = set()
    # Match visible text at the nearest declared language, preserving Arabic
    # quotations, code, and the exact bilingual name used on the profile.
    for el in doc.elements:
        if not el.within(lambda a: a.tag == "body") or el.within(lambda a: a.tag in ("script", "style", "code", "pre")):
            continue
        ancestor = el
        while ancestor is not None and not ancestor.get("lang"):
            ancestor = ancestor.parent
        if ancestor is None or ancestor.get("lang").split("-")[0] != "fa":
            continue
        for value in el.children:
            if isinstance(value, str):
                clean = value.replace(APPROVED_ARABIC_NAME, "")
                if re.search("[يك]", clean):
                    problems.add("Persian text contains Arabic yeh or kaf")
    return sorted(problems)


def graph_errors(graph, indexed, redirects):
    errors = []
    # Edges from redirects and noindex pages cannot rescue an orphan.
    inbound = {dest for src in indexed for dest in graph[src] if dest != src}
    for src, edges in graph.items():
        for dest in sorted(edges & redirects):
            errors.append(f"{src}: links to redirect {dest}")
    for locale in sorted({language(path) for path in indexed}):
        home = ("" if locale == "en" else locale + "/") + "index.html"
        depths = {home: 0}
        queue = deque([home])
        while queue:
            origin = queue.popleft()
            for dest in graph.get(origin, set()) & indexed:
                if dest not in depths:
                    depths[dest] = depths[origin] + 1
                    queue.append(dest)
        for path in sorted(p for p in indexed if language(p) == locale):
            if path != home and path not in inbound:
                errors.append(f"{path}: orphan")
            if depths.get(path, 4) > 3:
                errors.append(f"{path}: deeper than three clicks from {home}")
    return errors


def audit(root, budget=None):
    docs = {p.relative_to(root).as_posix(): Document(p.read_text()) for p in site_pages(root)}
    indexed, redirects, graph, errors, weights = set(), set(), {}, [], {}
    for path, doc in docs.items():
        expected = language(path)
        attrs = doc.tags("html")
        if not attrs:
            errors.append(f"{path}: missing HTML element")
            continue
        if attrs[0].get("lang").split("-")[0] != expected or (expected in ("fa", "ar") and attrs[0].get("dir") != "rtl"):
            errors.append(f"{path}: language or text direction differs from its URL")
        if any(el.get("http-equiv").lower() == "refresh" for el in doc.tags("meta")):
            redirects.add(path)
        elif doc.indexable() and doc.links("canonical"):
            indexed.add(path)
        graph[path] = {dest for el in doc.tags("a") if (dest := resolve(path, el.get("href"))) in docs}
        for link in doc.links("alternate"):
            code, href = link.get("hreflang"), link.get("href")
            if not code:
                continue
            target = resolve(path, href)
            expected_code = "en" if code == "x-default" else code
            if (target not in docs or language(target) != expected_code
                    or [el.get("href") for el in docs[target].links("canonical")] != [href]):
                errors.append(f"{path}: {code} alternate must resolve to a self-canonical {expected_code} page")
        if expected == "fa":
            errors.extend(f"{path}: {value}" for value in persian_typography(doc))
        for img in doc.tags("img"):
            if not all(re.fullmatch(r"[1-9]\d*", img.get(k)) for k in ("width", "height")):
                errors.append(f"{path}: image needs positive intrinsic dimensions: {img.get('src')}")
        weights[path] = page_weight(root, path, doc)
        limit = budget if budget is not None else (EXPLORER_BYTE_LIMIT if path == "studies/explorer.html" else INITIAL_BYTE_LIMIT)
        if weights[path] > limit:
            errors.append(f"{path}: initial asset budget exceeded: {weights[path]} > {limit}")
    return weights, errors + graph_errors(graph, indexed, redirects)


if __name__ == "__main__":
    weights, errors = audit(ROOT)
    for error in errors:
        print(error)
    print(f"{'FAIL' if errors else 'PASS'} page quality: {len(weights)} HTML files, {len(errors)} issues")
    sys.exit(bool(errors))
