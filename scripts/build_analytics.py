"""Install the guarded Cloudflare analytics loader on canonical, indexable site pages.

The sitemap is the public-page allowlist. Player embeds, 404 and verification documents
remain unmeasured. The loader itself permits only a-samadi.com and www.a-samadi.com,
so local previews and the direct GitHub hostname cannot report visits. Run --check before
publication; this script does not change Cloudflare account settings or collect test visits.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
TAG = '<script src="/js/site-analytics.js?v=20261009-analytics1" defer></script>'
LOADER = re.compile(r'<script\s+src="/js/site-analytics\.js(?:\?[^\"]*)?"\s+defer\s*></script>')
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = None
        self.robots = ''
        self.analytics = []
        self.direct_beacons = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'link' and values.get('rel') == 'canonical':
            self.canonical = values.get('href')
        if tag == 'meta' and values.get('name', '').lower() == 'robots':
            self.robots = values.get('content', '').lower()
        if tag == 'script':
            source = urlsplit(values.get('src', ''))
            if source.path.endswith('/site-analytics.js'):
                self.analytics.append(values)
            if 'data-cf-beacon' in values or source.netloc == 'static.cloudflareinsights.com':
                self.direct_beacons.append(values)


def public_pages():
    pages = {}
    for item in ElementTree.parse(ROOT / 'sitemap.xml').findall('s:url/s:loc', NS):
        url = item.text
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != 'a-samadi.com' or parsed.query or parsed.fragment:
            raise ValueError(f'Unexpected canonical sitemap URL: {url}')
        relative = parsed.path.lstrip('/')
        if not relative or relative.endswith('/'):
            relative += 'index.html'
        path = ROOT / relative
        if not path.is_file() or path.suffix != '.html' or ROOT not in path.resolve().parents:
            raise ValueError(f'Missing or invalid public HTML page: {url}')
        if path in pages:
            raise ValueError(f'Duplicate sitemap page: {url}')
        pages[path] = url
    return pages


def install(text):
    if len(LOADER.findall(text)) > 1:
        raise ValueError('Duplicate analytics loaders')
    if LOADER.search(text):
        return LOADER.sub(lambda _: TAG, text)
    if '</head>' not in text:
        raise ValueError('Missing head closing tag')
    return text.replace('</head>', '\n' + TAG + '\n</head>', 1)


def main():
    check = '--check' in sys.argv
    pages = public_pages()
    changed = 0
    if not (ROOT / 'js/site-analytics.js').is_file():
        raise ValueError('Missing guarded analytics loader')
    for path, url in pages.items():
        original = path.read_text()
        head = Head()
        head.feed(original.partition('</head>')[0])
        if head.canonical != url or 'noindex' in head.robots:
            raise ValueError(f'{path}: sitemap page must be self-canonical and indexable')
        if head.direct_beacons:
            raise ValueError(f'{path}: remove a duplicate direct beacon before installing the guarded loader')
        if len(head.analytics) > 1:
            raise ValueError(f'{path}: duplicate analytics loaders')
        if head.analytics and len(LOADER.findall(original)) != 1:
            raise ValueError(f'{path}: analytics must use the local deferred loader')
        updated = install(original)
        if updated != original:
            changed += 1
            print(('MISSING ' if check else 'Updated ') + path.relative_to(ROOT).as_posix() + ': analytics loader')
            if not check:
                if path.read_text() != original:
                    raise RuntimeError(f'{path}: changed concurrently; preserve the other edit')
                path.write_text(updated)
    excluded = 0
    for path in ROOT.rglob('*.html'):
        if path in pages or any(part in ('.git', 'node_modules') for part in path.relative_to(ROOT).parts):
            continue
        excluded += 1
        if 'site-analytics.js' in path.read_text() or 'data-cf-beacon' in path.read_text():
            raise ValueError(f'{path}: nonpublic page must not contain analytics')
    if check and changed:
        raise SystemExit(1)
    print(f'PASS analytics: {len(pages)} canonical indexable pages, {excluded} other HTML pages excluded; '
          + ('no changes needed' if not changed else f'{changed} updated'))


if __name__ == '__main__':
    main()
