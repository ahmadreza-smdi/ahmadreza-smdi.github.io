"""Inline applicable CSS on the explicitly enrolled, existing film pages.

Rebuild: install scripts/requirements-film-css.txt, then run this script.
Read-only --check uses only the standard library and verifies the reviewed
source/output hashes. --add-current explicitly enrolls current film pages;
ordinary rebuild/check does not change the scope or the frozen publishers.
Run after the other page and style generators. Dates, media and body markup
remain byte-for-byte unchanged. Unknown selectors are retained conservatively.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / 'locales/film-css.json'
LINK = re.compile(r'<link\b[^>]*\brel="stylesheet"[^>]*>')
HREF = re.compile(r'\bhref="([^"]+)"')
BLOCK = re.compile(r'<!-- film-css:start:([^ ]+) -->\n<style data-film-css="\1">\n(.*?)\n</style>\n<!-- film-css:end:\1 -->', re.S)
ALLOWED = {'css/site.css', 'css/rtl.css', 'css/author-box.css', 'css/property-guides.css'}
STATE_ATTR = re.compile(r'\[(?:open|hidden|aria-expanded|aria-current|aria-selected|aria-pressed|data-state|data-phase|data-paused)(?:[^\]]*)\]')
DYNAMIC = re.compile(r'(?<!:):(focus-visible|focus-within|hover|focus|active|visited|link|target)(?![\w-])')


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def safe_page(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix != '.html' or not path.is_file():
        raise ValueError('Invalid film page: ' + name)
    return path


def original_html(text, entry):
    sources = {row['source']: row for row in entry.get('sheets', [])}
    seen = set()
    def restore(match):
        name = match[1]
        if name not in sources or name in seen:
            raise ValueError('Unknown or duplicate generated film stylesheet: ' + name)
        seen.add(name)
        return sources[name]['original_link']
    result = BLOCK.sub(restore, text)
    if '<!-- film-css:' in result or 'data-film-css=' in result:
        raise ValueError('Malformed generated film stylesheet')
    return result


def extract(css, document, source):
    # These imports are deliberately rebuild-only. CI verification is stdlib.
    import tinycss2
    import cssselect2
    from lxml import html
    tree = cssselect2.ElementWrapper.from_html_root(html.fromstring(document))
    elements = list(tree.iter_subtree())
    unknown = set()
    counts = {'kept': 0, 'dropped': 0}
    def rewrite_urls(tokens):
        for token in tokens:
            if token.type == 'url':
                value = token.value
                if not value.startswith(('#', 'data:', 'https:', 'http:', '//')):
                    token.value = urljoin('/' + source, value)
                    token.representation = 'url(' + json.dumps(token.value) + ')'
            elif token.type == 'function':
                if token.lower_name == 'url':
                    significant = [x for x in token.arguments if x.type not in ('whitespace', 'comment')]
                    if len(significant) == 1 and significant[0].type == 'string':
                        item = significant[0]
                        if not item.value.startswith(('#', 'data:', 'https:', 'http:', '//')):
                            item.value = urljoin('/' + source, item.value)
                            item.representation = json.dumps(item.value)
                else:
                    rewrite_urls(token.arguments)
            elif hasattr(token, 'content') and token.content is not None:
                rewrite_urls(token.content)
    def rules(items):
        result = []
        for rule in items:
            if rule.type == 'qualified-rule':
                selector = tinycss2.serialize(rule.prelude)
                matching = STATE_ATTR.sub('', DYNAMIC.sub('', selector))
                try:
                    selectors = cssselect2.compile_selector_list(matching)
                    keep = any(s.test(el) for s in selectors for el in elements)
                except cssselect2.SelectorError:
                    keep = True
                    unknown.add(selector)
                counts['kept' if keep else 'dropped'] += 1
                if keep:
                    rewrite_urls(rule.content)
                    result.append(tinycss2.serialize([rule]))
            elif rule.type == 'at-rule':
                if rule.content is not None and rule.lower_at_keyword in ('media', 'supports', 'layer', 'container'):
                    nested = rules(tinycss2.parse_rule_list(rule.content, skip_comments=True, skip_whitespace=True))
                    if nested:
                        result.append('@' + rule.at_keyword + tinycss2.serialize(rule.prelude) + '{' + nested + '}')
                else:
                    if rule.content is not None:
                        rewrite_urls(rule.content)
                    result.append(tinycss2.serialize([rule]))
            elif rule.type == 'error':
                raise ValueError(rule.message)
        return ''.join(result)
    result = rules(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True))
    if '</style' in result.lower():
        raise ValueError('Stylesheet cannot safely be embedded in HTML')
    return result, {'rules': counts, 'conservative_selectors': sorted(unknown)}


def render(text, source_bytes):
    sheets = []
    seen = set()
    def replace(match):
        href = HREF.search(match[0])
        if not href:
            raise ValueError('Stylesheet has no href')
        parsed = urlsplit(href[1])
        source = parsed.path.lstrip('/')
        if parsed.netloc or not href[1].startswith('/') or source not in ALLOWED or source in seen:
            raise ValueError('Unreviewed or duplicate stylesheet: ' + href[1])
        seen.add(source)
        css, info = extract(source_bytes[source].decode(), text, source)
        sheets.append({'source': source, 'original_link': match[0], 'source_sha256': digest(source_bytes[source]), 'inline_sha256': digest(css), **info})
        return f'<!-- film-css:start:{source} -->\n<style data-film-css="{source}">\n{css}\n</style>\n<!-- film-css:end:{source} -->'
    result = LINK.sub(replace, text)
    if 'css/site.css' not in seen or '<video' not in text or 'class="editorial-body"' not in text:
        raise ValueError('Expected an existing editorial film page with site.css')
    return result, sheets


def check(root, config):
    if config.get('version') != 1 or not config.get('pages'):
        raise ValueError('Missing reviewed film CSS inventory')
    if config['generator_sha256'] != digest(Path(__file__).read_bytes()):
        raise ValueError('Generator changed; rebuild film CSS')
    sources = {s: (root / s).read_bytes() for s in ALLOWED}
    for name, entry in config['pages'].items():
        text = safe_page(root, name).read_text()
        original = original_html(text, entry)
        if digest(original) != entry['original_sha256'] or digest(text) != entry['output_sha256']:
            raise ValueError('Film page content or generated style changed; rebuild: ' + name)
        blocks = {m[1]: m[2] for m in BLOCK.finditer(text)}
        if len(blocks) != len(entry['sheets']):
            raise ValueError('Missing generated film styles: ' + name)
        for sheet in entry['sheets']:
            source = sheet['source']
            if source not in ALLOWED or digest(sources[source]) != sheet['source_sha256']:
                raise ValueError('Source CSS changed; rebuild: ' + source)
            if digest(blocks.get(source, '')) != sheet['inline_sha256']:
                raise ValueError('Generated CSS changed: ' + name)
    return len(config['pages'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--add-current', action='store_true', help='Explicitly enroll current editorial film pages')
    args = parser.parse_args()
    if args.check and args.add_current:
        parser.error('--check and --add-current are separate operations')
    old_manifest = MANIFEST.read_bytes() if MANIFEST.exists() else None
    config = json.loads(old_manifest) if old_manifest else {'version': 1, 'pages': {}}
    if args.check:
        print(f'PASS film CSS: {check(ROOT, config)} enrolled pages; source, content and output hashes match')
        return
    pages = dict(config['pages'])
    if args.add_current:
        for path in sorted(ROOT.rglob('*.html')):
            if any(p.startswith('.') for p in path.relative_to(ROOT).parts):
                continue
            text = path.read_text()
            if '<video' in text and 'class="editorial-body"' in text and '/css/site.css' in text:
                pages.setdefault(path.relative_to(ROOT).as_posix(), {})
    if not pages:
        raise ValueError('No enrolled film pages; review --add-current first')
    sources = {s: (ROOT / s).read_bytes() for s in ALLOWED}
    updates = []
    inventory = {}
    for name, entry in sorted(pages.items()):
        path = safe_page(ROOT, name)
        before = path.read_bytes()
        original = original_html(before.decode(), entry)
        after, sheets = render(original, sources)
        if original_html(after, {'sheets': sheets}) != original:
            raise ValueError('Non-style page change: ' + name)
        inventory[name] = {'original_sha256': digest(original), 'output_sha256': digest(after), 'sheets': sheets}
        updates.append((path, before, after.encode()))
    output = {'version': 1, 'generator_sha256': digest(Path(__file__).read_bytes()), 'pages': inventory}
    for source, data in sources.items():
        if (ROOT / source).read_bytes() != data:
            raise RuntimeError('Concurrent stylesheet edit: ' + source)
    for path, before, _ in updates:
        if path.read_bytes() != before:
            raise RuntimeError('Concurrent page edit: ' + str(path))
    if (MANIFEST.read_bytes() if MANIFEST.exists() else None) != old_manifest:
        raise RuntimeError('Concurrent manifest edit')
    for path, before, after in updates:
        if before != after:
            path.write_bytes(after)
    MANIFEST.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(f'PASS film CSS: {len(updates)} enrolled pages; {sum(b != a for _, b, a in updates)} updated; no body, date or media changes')


if __name__ == '__main__':
    main()
