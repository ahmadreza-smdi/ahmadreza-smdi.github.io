"""Build or check localized Article-to-topic and related-pillar links.

The approved English-first taxonomy is separate from editorial body text.
Template-only navigation changes preserve publication/modification dates.
"""
import argparse
from html import escape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://a-samadi.com/'
START = '<!-- article-hubs:start -->'
END = '<!-- article-hubs:end -->'
LABELS = {
    'en': {'part': 'Part of', 'related': 'Related'},
    'fa': {'part': 'بخشی از', 'related': 'مطالب مرتبط'},
    'ar': {'part': 'ضمن موضوع', 'related': 'محتوى ذو صلة'},
}

def prefix(language):
    return '' if language == 'en' else language + '/'

def resource(relative):
    if relative.startswith('/') or '..' in Path(relative).parts:
        raise ValueError(f'Unsafe local resource: {relative}')
    path = ROOT / relative
    text = path.read_text()
    from html import unescape
    match = re.search(r'<h1\b[^>]*>(.*?)</h1>', text, re.S)
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', text)
    if not match or not canonical or canonical[1] != BASE + relative:
        raise ValueError(f'Invalid local resource: {relative}')
    title = ' '.join(unescape(re.sub(r'<[^>]+>', ' ', match[1])).split())
    return '/' + relative, title

def render(family, language, hubs):
    labels = LABELS[language]
    hub = next(h for h in hubs if h['id'] == family['hub'])
    target = hub['paths'][language]
    href, _ = resource(target)
    title = hub['locales'][language]['heading']
    links = []
    destinations = set()
    pillars = set()
    for related in family['related']:
        relative = prefix(language) + related['path']
        if relative == family['paths'][language] or relative in destinations:
            raise ValueError(f'Duplicate or self related link: {relative}')
        destinations.add(relative)
        pillars.add(related['pillar'])
        related_href, related_title = resource(relative)
        links.append(f'<li><a href="{escape(related_href, quote=True)}" data-related-pillar="{escape(related["pillar"], quote=True)}">{escape(related_title)}</a></li>')
    allowed_pillars = (
        {'property-decisions', 'decision-first-ai', 'tech-explained'},
        {'property-decisions', 'decision-first-ai', 'building-business'},
    )
    if len(links) != 3 or pillars not in allowed_pillars:
        raise ValueError(f'Expected three distinct pillar links: {family["stem"]}')
    return f'''{START}
<nav class="article-reading-path" aria-labelledby="article-related-title">
<p>{escape(labels['part'])}: <a href="{escape(href, quote=True)}" data-hub-primary="{escape(family['hub'], quote=True)}">{escape(title)}</a></p>
<h2 id="article-related-title">{escape(labels['related'])}</h2>
<ul>{chr(10).join(links)}</ul>
</nav>
{END}
'''

def install(text, block):
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError('Duplicate or incomplete Article navigation markers')
    if START in text:
        return re.sub(re.escape(START) + r'.*?' + re.escape(END) + r'\n?', lambda _: block, text, count=1, flags=re.S)
    marker = '<!-- author-box:start -->'
    if text.count(marker) != 1:
        raise ValueError('Expected one end-author insertion point')
    return text.replace(marker, block + marker, 1)

def all_articles():
    found = set()
    for directory in ('writing', 'fa/writing', 'ar/writing'):
        for path in (ROOT / directory).glob('*.html'):
            text = path.read_text()
            graphs = [json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)]
            if any(node.get('@type') == 'Article' for graph in graphs for node in graph.get('@graph', [graph])):
                found.add(str(path.relative_to(ROOT)))
    return found

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data = json.loads((ROOT / 'locales/article-hubs.json').read_text())
    topic_data = json.loads((ROOT / 'locales/topic-hubs.json').read_text())
    if data.get('primary_language') != 'en':
        raise ValueError('English must remain the original')
    expected = {relative for family in data['families'] for relative in family['paths'].values()}
    if expected != all_articles():
        raise ValueError('Article taxonomy must cover exactly the current Article inventory')
    snapshots = []
    for family in data['families']:
        if set(family['paths']) != {'en', 'fa', 'ar'}:
            raise ValueError(f'Missing Article locale: {family["stem"]}')
        for language, relative in family['paths'].items():
            hub = next(h for h in topic_data['hubs'] if h['id'] == family['hub'])
            membership = {topic_data['resources'][key]['paths'].get(language, topic_data['resources'][key]['paths']['en']) for key in hub['ordered_resources']}
            if relative not in membership:
                raise ValueError(f'Article is missing from its primary hub: {relative}')
            path = ROOT / relative
            current = path.read_text()
            expected_text = install(current, render(family, language, topic_data['hubs']))
            snapshots.append((path, current, expected_text))
    stale = [row for row in snapshots if row[1] != row[2]]
    if args.check:
        for path, _, _ in stale:
            print('STALE', path.relative_to(ROOT))
        if stale:
            raise SystemExit(1)
        print(f'PASS Article hub navigation: {len(snapshots)} Articles, one primary hub and three distinct pillar links each')
        return
    for path, current, expected_text in stale:
        if path.read_text() != current:
            raise RuntimeError(f'Concurrent edit: {path}')
        path.write_text(expected_text)
    print(f'Built Article hub navigation: {len(stale)} changed / {len(snapshots)} Articles')

if __name__ == '__main__':
    main()
