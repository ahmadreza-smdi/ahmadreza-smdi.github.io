"""Maintain the supported author reference on article pages in their own language.

The top byline, article text, dates and metadata are left intact. Only the marked author
box and its dedicated stylesheet link are generated. Run --check before publication.
"""
from pathlib import Path
import re
import sys

from enrich_metadata import article_node, language

ROOT = Path(__file__).resolve().parent.parent
STYLESHEET = '<link rel="stylesheet" href="/css/author-box.css?v=20261009-author1">'
STYLE_LINK = re.compile(r'<link\s+rel="stylesheet"\s+href="/css/author-box\.css(?:\?[^\"]*)?"\s*/?>')
BOX = re.compile(r'<!-- author-box:start -->.*?<!-- author-box:end -->', re.S)
COPY = {
    'en': {
        'heading': 'About the author',
        'name': 'Ahmadreza Samadi',
        'about': '/about.html',
        'summary': 'Technology Entrepreneur based in Dubai. Co-Founder &amp; Technical Lead at Appraiva; Co-Founder &amp; CEO at Royal Abraj Group.',
    },
    'fa': {
        'heading': 'درباره نویسنده',
        'name': 'احمدرضا صمدی',
        'about': '/fa/about.html',
        'summary': 'کارآفرین فناوری ساکن دبی؛ هم‌بنیان‌گذار و راهبر فنی <bdi lang="en">Appraiva</bdi> و هم‌بنیان‌گذار و مدیرعامل گروه رویال ابراج.',
    },
    'ar': {
        'heading': 'عن الكاتب',
        'name': 'أحمدرضا صمدي',
        'about': '/ar/about.html',
        'summary': 'رائد أعمال تقني مقيم في دبي؛ شريك مؤسس وقائد تقني في <bdi lang="en">Appraiva</bdi> وشريك مؤسس ورئيس تنفيذي لمجموعة رويال أبراج.',
    },
}


def author_box(lang):
    copy = COPY[lang]
    return ('<!-- author-box:start -->\n'
            '<aside class="article-author" aria-labelledby="article-author-title">\n'
            f'<h2 id="article-author-title">{copy["heading"]}</h2>\n'
            f'<p class="article-author__name"><a href="{copy["about"]}" rel="author">{copy["name"]}</a></p>\n'
            f'<p>{copy["summary"]}</p>\n'
            '</aside>\n<!-- author-box:end -->')


def enrich_author(path, text):
    if not article_node(text)[1]:
        return text
    lang = language(text)
    if lang not in COPY:
        raise ValueError(f'{path}: no supported author copy for {lang}')
    if len(BOX.findall(text)) > 1 or len(STYLE_LINK.findall(text)) > 1:
        raise ValueError(f'{path}: duplicate author boxes or stylesheet links')
    box = author_box(lang)
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
    for prefix in ('writing', 'fa/writing', 'ar/writing'):
        for path in sorted((ROOT / prefix).glob('*.html')):
            original = path.read_text()
            if not article_node(original)[1]:
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
