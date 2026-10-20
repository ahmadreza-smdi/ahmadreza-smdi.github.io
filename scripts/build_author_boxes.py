"""Maintain the supported author reference on article pages in their own language.

The top byline, article text, dates and metadata are left intact. Only the marked author
box and its dedicated stylesheet link are generated. Run --check before publication.
"""
from pathlib import Path
import re
import json
from html import escape
import sys

from enrich_metadata import article_node, language

ROOT = Path(__file__).resolve().parent.parent
STYLESHEET = '<link rel="stylesheet" href="/css/author-box.css?v=20261009-author1">'
STYLE_LINK = re.compile(r'<link\s+rel="stylesheet"\s+href="/css/author-box\.css(?:\?[^\"]*)?"\s*/?>')
BIOS = json.loads((ROOT / 'locales/author-bios.json').read_text())
BOX = re.compile(r'<!-- author-box:start -->.*?<!-- author-box:end -->', re.S)
COPY = {
    'en': {
        'heading': 'About the author',
        'name': 'Ahmadreza Samadi',
        'about': '/about.html',
        'summary': escape(BIOS['en']),
    },
    'fa': {
        'heading': 'درباره نویسنده',
        'name': 'احمدرضا صمدی',
        'about': '/fa/about.html',
        'summary': escape(BIOS['fa']),
    },
    'ar': {
        'heading': 'عن الكاتب',
        'name': 'أحمدرضا صمدي',
        'about': '/ar/about.html',
        'summary': escape(BIOS['ar']),
    },
}


# Editorial essays use the ideas series. Property evidence and calculators use Data;
# the remaining explanatory articles belong to the daily technology series.
IDEA_ARTICLES = {
    'ai-agent-safety-boundaries.html', 'ai-cost-per-verified-result.html',
    'ai-document-review-claim-evidence-checklist.html', 'ai-human-review-real-estate.html',
    'connected-ai-apps.html', 'start-with-the-decision.html',
}
DATA_ARTICLES = {
    'ai-home-value-estimates.html', 'ai-rental-yield-cash-flow.html',
    'property-data-enrichment.html', 'which-dubai-property-source.html',
    'why-rent-to-value-is-not-property-yield.html',
}
SERIES_PREFIX = {'en': 'Part of', 'fa': 'از مجموعهٔ', 'ar': 'ضمن سلسلة'}


def series_for(path):
    parts = path.relative_to(ROOT).parts
    if parts[0] in ('fa', 'ar'):
        parts = parts[1:]
    if parts[0] in ('tools', 'studies') or path.name in DATA_ARTICLES:
        return 'Property Decision Data'
    if path.name in IDEA_ARTICLES:
        return 'Start with the Decision'
    return 'Tech, explained'


def author_box(lang, series=None):
    copy = COPY[lang]
    series_line = (f'<p class="article-author__series">{SERIES_PREFIX[lang]} '
                   f'<bdi lang="en">{escape(series)}</bdi></p>\n') if series else ''
    return ('<!-- author-box:start -->\n'
            '<aside class="article-author" aria-labelledby="article-author-title">\n'
            f'<h2 id="article-author-title">{copy["heading"]}</h2>\n'
            f'<p>{copy["summary"]}</p>\n'
            f'<p class="article-author__name"><a href="{copy["about"]}" rel="author">{copy["name"]}</a></p>\n'
            f'{series_line}'
            '</aside>\n<!-- author-box:end -->')


def enrich_author(path, text):
    if not article_node(text)[1] and not BOX.search(text):
        return text
    lang = language(text)
    if lang not in COPY:
        raise ValueError(f'{path}: no supported author copy for {lang}')
    if len(BOX.findall(text)) > 1 or len(STYLE_LINK.findall(text)) > 1:
        raise ValueError(f'{path}: duplicate author boxes or stylesheet links')
    box = author_box(lang, series_for(path))
    if BOX.search(text):
        text = BOX.sub(lambda _: box, text)
    else:
        footer = text.find('<footer class="editorial-footer">')
        if footer < 0:
            raise ValueError(f'{path}: no article footer for author reference')
        # Keep the author aside inside an existing article, or before its footer when the
        # older page layout uses main directly. Do not wrap or restructure existing content.
        end_article = text.rfind('</article>', 0, footer)
        insertion = end_article if end_article >= 0 else footer
        text = text[:insertion] + '\n' + box + '\n' + text[insertion:]
    if STYLE_LINK.search(text):
        text = STYLE_LINK.sub(lambda _: STYLESHEET, text)
    else:
        if '</head>' not in text:
            raise ValueError(f'{path}: missing head closing tag')
        text = text.replace('</head>', '\n' + STYLESHEET + '\n</head>', 1)
    return text


def main():
    check = '--check' in sys.argv
    count = changed = 0
    for path in sorted(ROOT.rglob('*.html')):
        if any(part.startswith('.') for part in path.relative_to(ROOT).parts):
            continue
        original = path.read_text()
        if not article_node(original)[1] and not BOX.search(original):
            continue
        count += 1
        updated = enrich_author(path, original)
        if updated == original:
            continue
        changed += 1
        print(('MISSING ' if check else 'Updated ') + path.relative_to(ROOT).as_posix() + ': author box')
        if not check:
            if path.read_text() != original:
                raise RuntimeError(f'{path}: changed concurrently; preserve the other edit')
            path.write_text(updated)
    if check and changed:
        raise SystemExit(1)
    print(f'PASS author boxes: {count} articles, ' + ('no changes needed' if not changed else f'{changed} updated'))


if __name__ == '__main__':
    main()
