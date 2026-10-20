"""Build full Persian/Arabic study pages from English without changing observations.

The table keys, source geography names, embedded numeric data and downloadable
artifacts remain the originals. All interface labels, messages and prose use the
locale catalogue. Missing visible translations fail the build.
"""
from pathlib import Path
from html import escape, unescape
from html.parser import HTMLParser
import json
import re
import sys
ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://a-samadi.com'
SOURCE = 'studies/rent-own-2026/index.html'
DATA_PATH = ROOT / 'locales/rent-study.json'

class Translate(HTMLParser):
    def __init__(self, source, lang, data):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.lang = lang
        self.data = data
        self.body = False
        self.skip = 0
        self.edits = []
        self.offsets = [0]
        for line in source.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
    def pos(self):
        line, col = self.getpos()
        return self.offsets[line-1] + col
    def translate(self, value):
        if value in self.data['text']:
            return self.data['text'][value][self.lang]
        if value in ('.', '·', 'YouTube', 'Instagram', 'LinkedIn', 'CC BY 4.0'):
            return value
        if value.startswith('Suggested citation:'):
            return {'fa':'استناد پیشنهادی (عنوان و نشانی اصلی): ', 'ar':'الاستشهاد المقترح (العنوان والرابط الأصليان): '}[self.lang] + value.removeprefix('Suggested citation: ')
        raise ValueError(f'Missing {self.lang} study translation: {value!r}')
    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self.body = True
        if tag in ('script', 'style', 'code', 'textarea'):
            self.skip += 1
        if not self.body:
            return
        raw = self.get_starttag_text()
        new = raw
        for key, value in attrs:
            if value is None:
                continue
            translated = value
            if key in ('aria-label', 'placeholder', 'alt'):
                translated = self.translate(value)
            elif key in ('href', 'src'):
                if value in ('metro-scenarios.csv', 'hud-area-scenarios.csv', 'rent-own-study-source.zip'):
                    translated = '/studies/rent-own-2026/' + value
                elif value in ('/about.html', '/writing/why-rent-to-value-is-not-property-yield.html', '/writing/'):
                    translated = '/' + self.lang + value
                elif value == BASE + '/about.html':
                    translated = BASE + '/' + self.lang + '/about.html'
                elif value == BASE + '/':
                    translated = BASE + '/' + self.lang + '/'
                elif value == BASE + '/studies/rent-own-2026/':
                    translated = BASE + '/' + self.lang + '/studies/rent-own-2026/'
                elif value == BASE + '/writing/ai-rental-yield-cash-flow.html':
                    translated = BASE + '/' + self.lang + '/writing/ai-rental-yield-cash-flow.html'
            if translated != value:
                new = re.sub(r'(' + re.escape(key) + r'\s*=\s*")([^"]*)(")', lambda m:m[1] + escape(translated, quote=True) + m[3], new)
        if raw != new:
            self.edits.append((self.pos(), self.pos()+len(raw), new))
    handle_startendtag = handle_starttag
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'code', 'textarea'):
            self.skip -= 1
    def handle_data(self, value):
        if not self.body or self.skip or not value.strip():
            return
        at = self.pos()
        end = self.source.find('<', at)
        raw = self.source[at:end]
        key = unescape(raw).strip()
        leading = raw[:len(raw)-len(raw.lstrip())]
        trailing = raw[len(raw.rstrip()):]
        self.edits.append((at, end, leading + escape(self.translate(key), quote=False) + trailing))


def build(lang):
    data = json.loads(DATA_PATH.read_text())
    source = (ROOT / SOURCE).read_text()
    page = data['locales'][lang]
    parser = Translate(source, lang, data)
    parser.feed(source)
    for start, end, replacement in sorted(parser.edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    canonical = BASE + '/' + lang + '/studies/rent-own-2026/'
    source = source.replace('<html lang="en">', '<html lang="' + lang + '" dir="rtl">', 1)
    source = re.sub(r'<title>.*?</title>', '<title>' + escape(page['title']) + '</title>', source, count=1)
    for key, kind in [('description','name'),('og:description','property'),('twitter:description','name')]:
        source = re.sub(r'(<meta ' + kind + '="' + key + r'" content=")[^"]*', lambda m:m[1] + escape(page['description'], quote=True), source)
    for key, kind in [('og:title','property'),('twitter:title','name')]:
        source = re.sub(r'(<meta ' + kind + '="' + key + r'" content=")[^"]*', lambda m:m[1] + escape(page['title'], quote=True), source)
    image_alt = {'fa':'اجاره، بودجهٔ مالکیت و بررسی شواهد — نمودار اصلی احمدرضا صمدی',
                 'ar':'الإيجار وميزانية التملّك والتحقق من الأدلة — رسم أصلي لأحمدرضا صمدي'}[lang]
    for key, kind in [('og:image:alt','property'),('twitter:image:alt','name')]:
        source = re.sub(r'(<meta ' + kind + '="' + key + r'" content=")[^"]*', lambda m:m[1] + image_alt, source)
    source = source.replace('rel="canonical" href="' + BASE + '/studies/rent-own-2026/"', 'rel="canonical" href="' + canonical + '"', 1)
    source = source.replace('property="og:url" content="' + BASE + '/studies/rent-own-2026/"', 'property="og:url" content="' + canonical + '"', 1)
    source = source.replace('property="og:locale" content="en_US"', 'property="og:locale" content="' + ('fa_IR' if lang=='fa' else 'ar_AE') + '"', 1)
    # Rebuild alternates for the current language in the common enricher below.
    source = re.sub(r'<meta property="og:locale:alternate" content="[^"]*"\s*/?>', '', source)
    source = source.replace('href="study.css?v=20261015-study2"', 'href="/studies/rent-own-2026/study.css?v=20261015-study2"')
    source = source.replace('src="study-ui.mjs?v=20261015-study2"', 'src="/studies/rent-own-2026/study-ui-localized.mjs?v=20261020-i18n1"')
    source = source.replace('</head>', '<link rel="stylesheet" href="/studies/rent-own-2026/study-rtl.css?v=20261020-i18n1"></head>', 1)
    def schema(match):
        graph = json.loads(match[1])
        for node in graph.get('@graph', [graph]):
            if node.get('@type') in ('WebApplication', 'Dataset'):
                fragment = '#app' if node['@type']=='WebApplication' else '#scenarios'
                node['url'] = canonical
                node['@id'] = canonical + fragment
                node['inLanguage'] = lang
                # The English source lists its translations. A translated node
                # instead identifies its matching original, never itself.
                node.pop('workTranslation', None)
                node['translationOfWork'] = {'@id': BASE + '/studies/rent-own-2026/' + fragment}
                if node['@type']=='WebApplication':
                    node['name'] = page['title']
                    node['description'] = page['description']
                    node['isBasedOn'] = {'@id': canonical + '#scenarios'}
                else:
                    node['name'] = page['title']
                    node['description'] = page['description']
        return '<script type="application/ld+json">' + json.dumps(graph, ensure_ascii=False, indent=2) + '</script>'
    source = re.sub(r'<script type="application/ld\+json">(.*?)</script>', schema, source, flags=re.S)
    # Input observations remain the exact English JSON. UI strings live separately.
    locale_data = json.dumps(page, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    source = source.replace('<script id="study-data"', '<script id="study-locale" type="application/json">' + locale_data + '</script><script id="study-data"', 1)
    if 'id="study-locale"' not in source:
        raise ValueError('Missing unchanged study data insertion anchor')
    # Retain common metadata (including the RTL font preload) on every rebuild
    # instead of overwriting additions made by the site-wide enricher.
    from enrich_metadata import enrich
    return enrich(ROOT / lang / SOURCE, source)[0]

if __name__ == '__main__':
    check = '--check' in sys.argv
    changed = []
    for lang in ('fa', 'ar'):
        path = ROOT / lang / SOURCE
        text = build(lang)
        old = path.read_text() if path.exists() else None
        if old == text:
            continue
        changed.append(str(path.relative_to(ROOT)))
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    print(('STALE ' if check and changed else 'PASS ') + 'rent study locales: ' + ', '.join(changed or ['no changes needed']))
    if check and changed:
        raise SystemExit(1)
