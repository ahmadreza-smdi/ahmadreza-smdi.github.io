"""Write /llms.txt: a plain-language map of the site for AI assistants and agents (llmstxt.org).

English pages come first and carry the descriptions; Persian and Arabic entry points are listed
under Optional. Titles and descriptions are read from the pages themselves, so the file stays in
step with the site. Run with --check to report whether llms.txt is out of date.
"""
from pathlib import Path
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
NOTES = (
    'Also known as Ahmad Samadi. Persian: احمدرضا صمدی; short form احمد صمدی. Arabic: أحمدرضا صمدي. '
    'Appraiva is based in Cleveland, Ohio, United States; he works remotely from Dubai. It builds AI tools '
    'that help real estate investors and developers find distressed and off-market properties through '
    'imagery analysis and enriched property data. Royal Abraj Group covers property brokerage and '
    'documents-clearing services; he leads its digital strategy and technology.\n\n'
    'English is the primary language of this site. Persian (/fa/) and Arabic (/ar/) pages are translations of the '
    'English originals and are linked to them with hreflang.\n\n'
    'Contact: ahmadreza.smdi@gmail.com. Facts on this site describe his own roles and work; the explainers and films '
    'use fictional teaching examples where they say so.\n\n'
    'Positioning, in his own words: "I build AI that helps people make better property decisions, and I run a '
    'property business in Dubai, so I know where the AI must stop."\n\n'
    'Series: Start with the Decision (ideas and newsletter); Property Decision Data (studies and tools); '
    'Tech, explained (plain-language articles and films).'
)
PROFILES = [
    ('LinkedIn', 'https://www.linkedin.com/in/ahmadreza-samadi/'),
    ('Instagram', 'https://www.instagram.com/ahmadreza_smdi/'),
    ('GitHub', 'https://github.com/ahmadreza-smdi'),
    ('Crunchbase', 'https://www.crunchbase.com/person/ahmadreza-samadi'),
    ('YouTube', 'https://www.youtube.com/@ahmadreza-samadi'),
    ('DEV', 'https://dev.to/ahmadreza_smdi'),
    ('Peerlist', 'https://peerlist.io/ahmadrezasmdi'),
    ('Product Hunt', 'https://www.producthunt.com/@ahmadreza_samadi'),
    ('Wellfound', 'https://wellfound.com/u/ahmadreza-samadi'),
]
BEST_PAGES = [
    ('AI property valuation', 'writing/ai-home-value-estimates.html'),
    ('Rent vs owning', 'studies/rent-own-2026/'),
    ('AI in real estate decisions: where AI should stop', 'writing/ai-human-review-real-estate.html'),
    ('Dubai property costs and data', 'writing/which-dubai-property-source.html'),
]


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
    return 'Profile'


def build():
    groups = {name: [] for name in ('Profile', 'Work', 'Topics', 'Writing', 'Films', 'Tools')}
    for url, text in entries():
        name = section(url)
        if name:
            label = {BASE: 'Homepage', BASE + 'about.html': 'Biography'}.get(url) or title(text)
            groups[name].append(f'- [{label}]({url}): {meta(text, "description")}')
    lines = ['# Ahmadreza Samadi', '', f'> {SUMMARY}', '', NOTES, '']
    lines += ['## Four main topics', '', *[
        f'- [{label}]({BASE}{path})' for label, path in BEST_PAGES
    ], '']
    for name, items in groups.items():
        if items:
            lines += [f'## {name}', '', *items, '']
    resources = public_resources((ROOT / 'about.html').read_text())
    if resources:
        lines += ['## Public code and data', '', *[f'- [{label}]({url}): {description}' for label, url, description in resources], '']
    lines += ['## Official profiles', '', *[f'- [{label}]({url})' for label, url in PROFILES], '']
    lines += [
        '## Optional', '',
        f'- [Persian homepage]({BASE}fa/): the site in Persian',
        f'- [Arabic homepage]({BASE}ar/): the site in Arabic',
        f'- [Persian writing]({BASE}fa/writing/): Persian translations of the articles',
        f'- [Arabic writing]({BASE}ar/writing/): Arabic translations of the articles',
        f'- [Homepage work index (JSON)]({BASE}ask-index.json): existing homepage passages and destinations in English, Persian and Arabic.',
        f'- [RSS feed]({BASE}writing/feed.xml): new English articles',
        f'- [Sitemap]({BASE}sitemap.xml): every page with its language alternates',
        '',
    ]
    return '\n'.join(lines)


def main():
    target = ROOT / 'llms.txt'
    content = build()
    if '--check' in sys.argv:
        if not target.is_file() or target.read_text() != content:
            print('MISSING or out of date: llms.txt (run python3 scripts/build_llms.py)')
            sys.exit(1)
        print('PASS llms.txt: up to date')
        return
    target.write_text(content)
    print(f'Wrote llms.txt ({len(content):,} characters)')


if __name__ == '__main__':
    main()
