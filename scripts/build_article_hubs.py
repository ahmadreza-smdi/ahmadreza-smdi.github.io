"""Build or check localized Article-to-topic and related-pillar links.

The approved English-first taxonomy is separate from editorial body text.
Template-only navigation changes preserve publication/modification dates.
"""
import argparse
from html import escape, unescape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://a-samadi.com/'
START = '<!-- article-hubs:start -->'
END = '<!-- article-hubs:end -->'
LABELS = {
    'en': {'part': 'Part of', 'related': 'Related', 'watch': 'Watch the accompanying film (English)'},
    'fa': {'part': 'بخشی از', 'related': 'مطالب مرتبط', 'watch': 'تماشای فیلم همراه این مطلب (انگلیسی)'},
    'ar': {'part': 'ضمن موضوع', 'related': 'محتوى ذو صلة', 'watch': 'شاهد الفيديو المرافق لهذا المقال (بالإنجليزية)'},
}

def prefix(language):
    return '' if language == 'en' else language + '/'

def resource(relative):
    if relative.startswith('/') or '..' in Path(relative).parts:
        raise ValueError(f'Unsafe local resource: {relative}')
    path = ROOT / (relative + 'index.html' if relative.endswith('/') else relative)
    text = path.read_text()
    from html import unescape
    match = re.search(r'<h1\b[^>]*>(.*?)</h1>', text, re.S)
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', text)
    if not match or not canonical or canonical[1] != BASE + relative:
        raise ValueError(f'Invalid local resource: {relative}')
    title = ' '.join(unescape(re.sub(r'<[^>]+>', ' ', match[1])).split())
    return '/' + relative, title

def render(family, language, hubs, membership=None, trail=None):
    labels = LABELS[language]
    hub = next(h for h in hubs if h['id'] == family['hub'])
    target = hub['paths'][language]
    href, _ = resource(target)
    title = hub['locales'][language]['heading']
    primary = f'<a href="{escape(href, quote=True)}" data-hub-primary="{escape(family["hub"], quote=True)}">{escape(title)}</a>'
    location = f"{escape(labels['part'])}: {primary}"
    if trail:
        home, breadcrumb = trail
        location = (f'<span role="navigation" aria-label="{escape(breadcrumb)}"><a href="/{prefix(language)}">{escape(home)}</a> / '
                    f'{primary}</span>')
    for other in membership or ():
        if other['id'] != hub['id']:
            location += (f' · <a href="/{escape(other["paths"][language], quote=True)}" data-hub-secondary="{escape(other["id"], quote=True)}">'
                         f'{escape(other["locales"][language]["heading"])}</a>')
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
    watch = ''
    if family.get('watch'):
        if not re.fullmatch(r'watch/[a-z0-9-]+\.html', family['watch']):
            raise ValueError(f'Expected a public English watch page: {family["stem"]}')
        watch_href, _ = resource(family['watch'])
        watch = f'<p><a href="{escape(watch_href, quote=True)}" hreflang="en">{escape(labels["watch"])}</a></p>\n'
    return f'''{START}
<nav class="article-reading-path" aria-labelledby="article-related-title">
<p>{location}</p>
{watch}<h2 id="article-related-title">{escape(labels['related'])}</h2>
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


TOP_TRAIL = re.compile(r'<nav\b[^>]*class="byline"[^>]*aria-label="[^"]+"[^>]*>\s*<a href="/(?:fa/|ar/)?">(?:(?!</nav>).)*?</nav>', re.S)
LIST_ITEMS = re.compile(r'("@type"\s*:\s*"BreadcrumbList"\s*,\s*(?:"@id"\s*:\s*"[^"]+"\s*,\s*)?"itemListElement"\s*:\s*)(\[\s*\{[^\[\]]*?\}\s*\])')
CRUMB_LABELS = {'en': ('Home', 'Breadcrumb'), 'fa': ('خانه', 'مسیر صفحه'), 'ar': ('الرئيسية', 'مسار الصفحة')}


def align_trail(text, relative, language, hub):
    home, label = CRUMB_LABELS[language]
    hub_title = hub['locales'][language]['heading']
    hub_path = hub['paths'][language]
    top = TOP_TRAIL.search(text)
    if top:
        markup = top[0]
        anchors = list(re.finditer(r'<a href="([^"]+)">([^<]*)</a>', markup))
        if len(anchors) != 2:
            raise ValueError(f'Unexpected top breadcrumb: {relative}')
        home = unescape(anchors[0][2])
        parent = f'<a href="/{hub_path}">{escape(hub_title)}</a>'
        text = text[:top.start()] + markup[:anchors[1].start()] + parent + '</nav>' + text[top.end():]
    # The article heading already names the current page. Show its two ancestors
    # in both trails so a long duplicate headline cannot displace the article.
    items = [(home, BASE + prefix(language)), (hub_title, BASE + hub_path)]
    def align_schema(match):
        value = json.loads(match[2])
        if len(value) not in (2, 3) or value[0].get('item') != items[0][1]:
            raise ValueError(f'Unexpected article breadcrumb: {relative}')
        expected = [{'@type': 'ListItem', 'position': i, 'name': name, 'item': target}
                    for i, (name, target) in enumerate(items, 1)]
        indent = re.search(r'\n( *)"itemListElement"', match[1])
        if indent:
            encoded = json.dumps(expected, ensure_ascii=False, indent=2).replace('\n', '\n' + indent[1])
        else:
            encoded = json.dumps(expected, ensure_ascii=False)
        return match[1] + encoded
    text, count = LIST_ITEMS.subn(align_schema, text)
    if count != 1:
        raise ValueError(f'Expected one structured article breadcrumb: {relative}')
    return text, None if top else (home, label)

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
            memberships = [h for h in topic_data['hubs'] if any(topic_data['resources'][k]['paths'].get(language) == relative for k in h['ordered_resources'])]
            text, trail = align_trail(current, relative, language, hub)
            expected_text = install(text, render(family, language, topic_data['hubs'], memberships, trail))
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
