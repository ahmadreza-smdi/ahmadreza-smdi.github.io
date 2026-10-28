"""Build a curated /llms.txt and a complete /llms-full.txt from the public site.

English pages come first and carry the descriptions; Persian and Arabic entry points are listed
under Optional. Titles and descriptions are read from the pages themselves, so the file stays in
step with the site. Run with --check to validate both outputs and description lengths.
"""
from pathlib import Path
from build_profile_facts import FACTS
from html.parser import HTMLParser
import html
import re
import sys
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://a-samadi.com/'
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
SUMMARY = (
    'Ahmadreza Samadi is a Dubai-based technology entrepreneur, Co-Founder & Technical Lead of Appraiva, '
    'which builds AI real estate intelligence, and Co-Founder & CEO of Royal Abraj Group.'
)
NOTES = 'Also known as Ahmad Samadi. Persian: احمدرضا صمدی; short form احمد صمدی. Arabic: أحمدرضا صمدي.'
PROFILES = [
    ('GitHub', 'https://github.com/ahmadreza-smdi', 'Ahmadreza Samadi’s public GitHub profile, connecting his repositories with the personal website.'),
    ('YouTube', 'https://www.youtube.com/@ahmadreza-samadi', 'Ahmadreza Samadi’s YouTube channel, connecting published explainer films with his personal website.'),
    ('DEV', 'https://dev.to/ahmadreza_smdi', 'Ahmadreza Samadi’s DEV profile, connecting published technical writing with his personal website.'),
    ('LinkedIn', 'https://www.linkedin.com/in/ahmadreza-samadi/', 'Professional profile listed by Ahmadreza Samadi as an official account on his biography page.'),
    ('Instagram', 'https://www.instagram.com/ahmadreza_smdi/', 'Instagram profile listed by Ahmadreza Samadi as an official account on his biography page.'),
    ('Crunchbase', 'https://www.crunchbase.com/person/ahmadreza-samadi', 'Crunchbase profile listed in the biography; public access and its website backlink remain unverified.'),
    ('Peerlist', 'https://peerlist.io/ahmadrezasmdi', 'Peerlist profile listed by Ahmadreza Samadi as an official account on his biography page.'),
    ('Product Hunt', 'https://www.producthunt.com/@ahmadreza_samadi', 'Product Hunt profile listed by Ahmadreza Samadi as an official account on his biography page.'),
    ('Wellfound', 'https://wellfound.com/u/ahmadreza-samadi', 'Wellfound profile listed by Ahmadreza Samadi as an official account on his biography page.'),
]
# Primary destinations are intentionally stable as the complete catalogue grows.
CORE_PATHS = (
    '', 'about.html', 'press.html',
    'work/appraiva.html', 'work/royal-abraj.html', 'work/oxfam-novib.html', 'work/mci.html',
    'studies/', 'studies/rent-own-2026/', 'studies/rent-burden/',
    'tools/before-you-build-ai.html', 'tools/rental-cash-flow.html',
    'tools/dubai-purchase-cost.html', 'tools/valuation-range.html', 'tools/dubai-rental-yield.html',
    'writing/ai-home-value-estimates.html', 'writing/ai-human-review-real-estate.html',
    'writing/which-dubai-property-source.html', 'writing/avm-vs-appraisal.html',
    'writing/property-comparables-evidence.html', 'writing/rent-or-buy-five-numbers.html',
    'writing/why-rent-to-value-is-not-property-yield.html', 'writing/start-with-the-decision.html',
    'writing/ai-cost-per-verified-result.html', 'writing/ai-rental-yield-cash-flow.html',
    'writing/property-data-enrichment.html', 'writing/ai-agent-safety-boundaries.html',
)
GROUPS = ('Profile', 'Work', 'Studies', 'Topics', 'Writing', 'Films', 'Tools', 'Explainers')
RESOURCE_DESCRIPTIONS = {
    'AI workflow cost ledger': 'AI workflow cost ledger includes retries, failed attempts and caller-defined acceptance; the workbook and worked examples are fictional.',
    'ACS2024 metro rent burden': 'ACS2024 metro rent-burden data with a CSV, chart, method and limits; not a property-level estimate.',
}


class PublicResourceParser(HTMLParser):
    """Read only visible list items in the existing public-tools-data block."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.item = None
        self.in_link = False
        self.resources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div':
            if self.depth:
                self.depth += 1
            elif 'public-tools-data' in (attrs.get('class') or '').split():
                self.depth = 1
        if not self.depth:
            return
        if tag == 'li':
            if self.item is not None:
                raise ValueError('Nested public resource list item')
            self.item = {'text': [], 'label': [], 'url': None}
        elif tag == 'a' and self.item is not None:
            href = attrs.get('href', '')
            if href.startswith('https://github.com/ahmadreza-smdi/'):
                if self.item['url'] is not None:
                    raise ValueError('Multiple public code links in one resource')
                self.item['url'] = href
                self.in_link = True

    def handle_data(self, text):
        if self.depth and self.item is not None:
            self.item['text'].append(text)
            if self.in_link:
                self.item['label'].append(text)

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == 'a':
            self.in_link = False
        elif tag == 'li' and self.item is not None:
            item = self.item
            self.item = None
            if item['url']:
                label = re.sub(r'\s+', ' ', ''.join(item['label'])).strip()
                text = re.sub(r'\s+', ' ', ''.join(item['text'])).strip()
                if not label or not text.startswith(label):
                    raise ValueError('Public resource must begin with its linked label')
                description = text[len(label):].lstrip(' —–-:')
                if not description:
                    raise ValueError('Public resource description is missing')
                if any(url == item['url'] for _, url, _ in self.resources):
                    raise ValueError('Duplicate public resource URL')
                self.resources.append((label, item['url'], description))
        elif tag == 'div':
            self.depth -= 1


def public_resources(text):
    parser = PublicResourceParser()
    parser.feed(text)
    parser.close()
    if parser.depth or parser.item is not None:
        raise ValueError('Incomplete public resource block')
    return parser.resources


def page_for(url):
    relative = url.replace(BASE, '', 1)
    return ROOT / (relative + 'index.html' if relative == '' or relative.endswith('/') else relative)


def meta(text, name):
    match = re.search(r'<meta\s+name="' + name + r'"\s+content="([^"]*)"', text)
    return html.unescape(match[1]).strip() if match else ''


def title(text):
    match = re.search(r'<title>([^<]*)</title>', text)
    value = html.unescape(match[1]).strip() if match else ''
    return re.sub(r'\s*\|\s*Ahmadreza Samadi$', '', value)


def entries():
    tree = ElementTree.parse(ROOT / 'sitemap.xml')
    for loc in tree.getroot().findall('s:url/s:loc', NS):
        url = loc.text.strip()
        page = page_for(url)
        if page.is_file():
            yield url, page.read_text()


def section(url):
    path = url.replace(BASE, '', 1)
    if path.startswith(('fa/', 'ar/')):
        return None
    if path in ('', 'about.html'):
        return 'Profile'
    if path.startswith('work/'):
        return 'Work'
    if path.startswith('tools/'):
        return 'Tools'
    if path.startswith('watch/'):
        return 'Films'
    if path.startswith('topics/'):
        return 'Topics'
    if path.startswith('writing/'):
        return 'Writing'
    if path.startswith('studies/'):
        return 'Studies'
    if path.startswith('carousels/'):
        return 'Explainers'
    return 'Profile'


def description(value, url):
    """Keep complete source descriptions; never silently truncate a factual qualification."""
    count = len(value.split())
    if not 10 <= count <= 30:
        raise ValueError(f'{url}: description must have 10–30 words; found {count}')
    return value


def entry(label, url, copy, film=None):
    suffix = f' (article + [film]({film}))' if film else ''
    return f'- [{label}]({url}){suffix}: {description(copy, url)}'


def facts():
    return '\n'.join(line.replace(' The start month is not stated.', '')
                     for line in FACTS.splitlines() if not line.startswith('- Spoken languages'))


def catalogue(pages, curated):
    groups = {name: [] for name in GROUPS}
    chosen = {BASE + path for path in CORE_PATHS}
    missing = chosen - pages.keys()
    if missing:
        raise ValueError('Missing curated destinations: ' + ', '.join(sorted(missing)))
    for url, text in pages.items():
        name = section(url)
        if name and (not curated or url in chosen):
            label = {BASE: 'Homepage', BASE + 'about.html': 'Biography'}.get(url) or title(text)
            film = None
            if curated and url.startswith(BASE + 'writing/'):
                links = re.findall(r'<a\b[^>]*href="(/watch/[^"#?]+\.html)"', text)
                film = next((BASE.rstrip('/') + path for path in links if BASE.rstrip('/') + path in pages), None)
            groups[name].append(entry(label, url, meta(text, 'description'), film))
    lines = ['# Ahmadreza Samadi', '', f'> {SUMMARY}', '', NOTES, '', facts(), '']
    for name, items in groups.items():
        if items:
            lines += [f'## {name}', '', *items, '']
    if not curated:
        resources = public_resources((ROOT / 'about.html').read_text())
        if resources:
            lines += ['## Public code and data', '', *[
                entry(label, url, RESOURCE_DESCRIPTIONS.get(label, copy)) for label, url, copy in resources], '']
    lines += ['## Official profiles', '', *[entry(*profile) for profile in PROFILES], '']
    if curated:
        lines += ['## Complete catalogue', '', entry('Full site catalogue', BASE + 'llms-full.txt',
                  'All English pages, films, public code resources, translated entry points and machine-readable discovery files.'), '']
    else:
        optional = [
            ('Persian homepage', 'fa/', 'Persian translation of the homepage, with the same supported identity, roles and selected work.'),
            ('Arabic homepage', 'ar/', 'Arabic translation of the homepage, with the same supported identity, roles and selected work.'),
            ('Persian writing', 'fa/writing/', 'Persian article index with translated titles, summaries and links to the corresponding reading pages.'),
            ('Arabic writing', 'ar/writing/', 'Arabic article index with translated titles, summaries and links to the corresponding reading pages.'),
            ('Homepage work index (JSON)', 'ask-index.json', 'Existing homepage passages and destinations in English, Persian and Arabic, exported from the visible source.'),
            ('RSS feed', 'writing/feed.xml', 'English article summaries with canonical links and original publication dates, generated from the published pages.'),
            ('Sitemap', 'sitemap.xml', 'Canonical indexable pages and their language alternates; embedded players and calculators are excluded.'),
        ]
        lines += ['## Optional', '', *[entry(label, BASE + path, copy) for label, path, copy in optional], '']
    return '\n'.join(lines)


def build():
    pages = dict(entries())
    return {'llms.txt': catalogue(pages, curated=True), 'llms-full.txt': catalogue(pages, curated=False)}


def main():
    outputs = build()
    if '--check' in sys.argv:
        stale = [name for name, content in outputs.items()
                 if not (ROOT / name).is_file() or (ROOT / name).read_text() != content]
        if stale:
            print('MISSING or out of date: ' + ', '.join(stale) + ' (run python3 scripts/build_llms.py)')
            sys.exit(1)
        print('PASS llms.txt and llms-full.txt: current; all descriptions contain 10–30 words')
        return
    for name, content in outputs.items():
        (ROOT / name).write_text(content)
        print(f'Wrote {name} ({len(content):,} characters)')


if __name__ == '__main__':
    main()
