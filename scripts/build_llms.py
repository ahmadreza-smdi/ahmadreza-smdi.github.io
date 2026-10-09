"""Write /llms.txt: a plain-language map of the site for AI assistants and agents (llmstxt.org).

English pages come first and carry the descriptions; Persian and Arabic entry points are listed
under Optional. Titles and descriptions are read from the pages themselves, so the file stays in
step with the site. Run with --check to report whether llms.txt is out of date.
"""
from pathlib import Path
import html
import re
import sys
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://a-samadi.com/'
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
SUMMARY = (
    'Official website of Ahmadreza Samadi (also Ahmad Samadi; Persian: احمدرضا صمدی; Arabic: أحمدرضا صمدي), '
    'a Dubai-based technology entrepreneur. He is Co-Founder & Technical Lead at Appraiva, a US-based company in '
    'Cleveland, Ohio, building AI real estate intelligence (he works remotely), and Co-Founder & CEO of Royal Abraj '
    'Group, a Dubai business spanning property brokerage and documents-clearing services.'
)
NOTES = (
    'English is the primary language of this site. Persian (/fa/) and Arabic (/ar/) pages are translations of the '
    'English originals and are linked to them with hreflang.\n\n'
    'Contact: ahmadreza.smdi@gmail.com. Facts on this site describe his own roles and work; the explainers and films '
    'use fictional teaching examples where they say so.'
)
PROFILES = [
    ('LinkedIn', 'https://www.linkedin.com/in/ahmadreza-samadi/'),
    ('Instagram', 'https://www.instagram.com/ahmadreza_smdi/'),
    ('GitHub', 'https://github.com/ahmadreza-smdi'),
    ('Crunchbase', 'https://www.crunchbase.com/person/ahmadreza-samadi'),
    ('YouTube', 'https://www.youtube.com/@ahmadreza-samadi'),
]


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
    if path.startswith('writing/'):
        return 'Writing'
    return 'Profile'


def build():
    groups = {name: [] for name in ('Profile', 'Work', 'Writing', 'Films', 'Tools')}
    for url, text in entries():
        name = section(url)
        if name:
            label = {BASE: 'Homepage', BASE + 'about.html': 'Biography'}.get(url) or title(text)
            groups[name].append(f'- [{label}]({url}): {meta(text, "description")}')
    lines = ['# Ahmadreza Samadi', '', f'> {SUMMARY}', '', NOTES, '']
    for name, items in groups.items():
        if items:
            lines += [f'## {name}', '', *items, '']
    lines += ['## Official profiles', '', *[f'- [{label}]({url})' for label, url in PROFILES], '']
    lines += [
        '## Optional', '',
        f'- [Persian homepage]({BASE}fa/): the site in Persian',
        f'- [Arabic homepage]({BASE}ar/): the site in Arabic',
        f'- [Persian writing]({BASE}fa/writing/): Persian translations of the articles',
        f'- [Arabic writing]({BASE}ar/writing/): Arabic translations of the articles',
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
