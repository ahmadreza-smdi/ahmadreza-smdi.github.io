"""Build the three factual press/media resource pages from approved public copy.

Content lives in locales/press.json. The English bios must still match the current public
biography; update all languages together when that biography changes. Existing portraits,
monogram, profile ZIP and contact card are linked directly. No Article dates, press coverage,
speaking history or new personal claims are generated. Run --check before publication.
"""
from html import escape
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://a-samadi.com'
LOCALES = {'en': 'en_US', 'fa': 'fa_IR', 'ar': 'ar_AE'}
OG_IMAGE = BASE + '/assets/img/ahmadreza-samadi-og.jpg'


def mixed(value, lang):
    text = escape(value)
    if lang != 'en':
        for name in ('Ahmadreza Samadi', 'Ahmad Samadi', 'Appraiva', 'Oxfam Novib', 'MCI', 'Bayshire Realty', 'JPG', 'SVG'):
            text = text.replace(name, '<bdi lang="en">' + name + '</bdi>')
    return text


def validate(data):
    public_bio = (ROOT / 'assets/profile/ahmadreza-samadi-bio.txt').read_text()
    short = public_bio.split('SHORT BIOGRAPHY\n\n', 1)[1].split('\n\nEXTENDED BIOGRAPHY', 1)[0].strip()
    extended = public_bio.split('EXTENDED BIOGRAPHY\n\n', 1)[1].split('\nWebsite:', 1)[0].strip().split('\n\n')
    english = data['pages']['en']
    if english['short_bio'] != short or english['extended_bio'] != extended:
        raise ValueError('Update press biography copy in all languages to match the current approved public biography')
    if data['primary_language'] != 'en' or data['email'] != 'ahmadreza.smdi@gmail.com':
        raise ValueError('Press resources must use English first and the personal email')
    for resource in data['resources']:
        path = ROOT / resource['path'].lstrip('/')
        if not path.is_file():
            raise ValueError('Missing approved public resource: ' + resource['path'])
    for lang, page in data['pages'].items():
        expected = '/press.html' if lang == 'en' else f'/{lang}/press.html'
        if page['path'] != expected or page['dir'] != ('ltr' if lang == 'en' else 'rtl'):
            raise ValueError('Incorrect press locale destination or direction')


def schema(data, lang):
    copy = data['pages'][lang]
    url = BASE + copy['path']
    page = {
        '@type': 'WebPage', '@id': url + '#press', 'url': url,
        'name': copy['title'], 'description': copy['description'], 'inLanguage': lang,
        'isPartOf': {'@id': BASE + '/#website'},
        'mainEntity': {'@id': BASE + '/#person'},
        'author': {'@id': BASE + '/#person'},
        'primaryImageOfPage': {
            '@type': 'ImageObject', 'url': BASE + data['portrait_display']['src'],
            'width': 900, 'height': 1200, 'caption': copy['portrait_alt'],
        },
        'image': BASE + data['portrait_display']['src'],
        'breadcrumb': {'@id': url + '#breadcrumbs'},
    }
    if lang == 'en':
        page['workTranslation'] = [{'@id': BASE + data['pages'][other]['path'] + '#press'} for other in ('fa', 'ar')]
    else:
        page['translationOfWork'] = {'@id': BASE + '/press.html#press'}
    breadcrumb = {
        '@type': 'BreadcrumbList', '@id': url + '#breadcrumbs',
        'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': copy['home'], 'item': BASE + copy['home_path']},
            {'@type': 'ListItem', 'position': 2, 'name': copy['h1'], 'item': url},
        ],
    }
    return {'@context': 'https://schema.org', '@graph': [page, breadcrumb]}


def build(data, lang):
    copy = data['pages'][lang]
    url = BASE + copy['path']
    direction = ' dir="rtl"' if lang != 'en' else ''
    body_class = 'editorial-body press-page' + (' persian-page' if lang == 'fa' else ' arabic-page' if lang == 'ar' else '')
    parts = ['<!doctype html>', f'<html lang="{lang}"{direction}>', '<head>',
             '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta name="author" content="Ahmadreza Samadi">',
             f'<title>{escape(copy["title"])}</title>',
             f'<meta name="description" content="{escape(copy["description"])}">',
             '<meta name="robots" content="index, follow, max-image-preview:large">',
             f'<link rel="canonical" href="{url}">']
    parts.extend(f'<link rel="alternate" hreflang="{code}" href="{href}">' for code, href in data['hreflang'].items())
    parts += ['<link rel="icon" type="image/svg+xml" href="/assets/brand/favicon.svg">']
    if lang != 'en':
        parts.append('<link rel="preload" as="font" type="font/woff2" href="/assets/fonts/vazirmatn-arabic-wght.woff2" crossorigin>')
    parts += ['<link rel="stylesheet" href="/css/site.css?v=20261009-lagoon4">']
    if lang != 'en':
        parts.append('<link rel="stylesheet" href="/css/rtl.css?v=20261009-lagoon4">')
    parts += ['<link rel="stylesheet" href="/css/press.css?v=20261009-press1">',
              '<meta property="og:type" content="website">',
              '<meta property="og:site_name" content="Ahmadreza Samadi">',
              f'<meta property="og:title" content="{escape(copy["title"])}">',
              f'<meta property="og:description" content="{escape(copy["description"])}">',
              f'<meta property="og:url" content="{url}">',
              f'<meta property="og:locale" content="{LOCALES[lang]}">']
    parts.extend(f'<meta property="og:locale:alternate" content="{LOCALES[code]}">' for code in LOCALES if code != lang)
    parts += [f'<meta property="og:image" content="{OG_IMAGE}">',
              '<meta property="og:image:type" content="image/jpeg">',
              '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
              f'<meta property="og:image:alt" content="{escape(copy["portrait_alt"])}">',
              '<meta name="twitter:card" content="summary_large_image">',
              f'<meta name="twitter:title" content="{escape(copy["title"])}">',
              f'<meta name="twitter:description" content="{escape(copy["description"])}">',
              f'<meta name="twitter:image" content="{OG_IMAGE}">',
              f'<meta name="twitter:image:alt" content="{escape(copy["portrait_alt"])}">',
              '<script type="application/ld+json">' + json.dumps(schema(data, lang), ensure_ascii=False, indent=2) + '</script>',
              '<script src="/js/site-analytics.js?v=20261009-analytics1" defer></script>',
              '</head>', f'<body class="{body_class}">',
              f'<a class="skip-link" href="#main">{escape(copy["skip"])}</a>',
              f'<header class="editorial-header"><a href="{copy["home_path"]}"><img src="/assets/brand/ahmadreza-samadi-mark-azure.svg" alt="" width="44" height="28">{escape(copy["name"])} / {escape(copy["home"])}</a></header>',
              '<main id="main" class="editorial">', '<div class="press-intro"><div>',
              f'<p class="eyebrow">{escape(copy["name"])}</p>', f'<h1>{escape(copy["h1"])}</h1>',
              f'<p class="lead">{escape(copy["lead"])}</p>',
              '<div class="profile-downloads">',
              f'<a href="/assets/profile/ahmadreza-samadi-profile-kit.zip" download>{escape(copy["resource_labels"]["kit"])}</a>',
              f'<a href="#press-contact">{escape(copy["contact_heading"])}</a>', '</div></div>',
              '<figure class="press-portrait">',
              f'<img src="{data["portrait_display"]["src"]}" srcset="{data["portrait_display"]["srcset"]}" sizes="(max-width: 259px) calc(100vw - 54px), 206px" alt="{escape(copy["portrait_alt"])}" width="900" height="1200" decoding="async">',
              f'<figcaption>{escape(copy["portrait_caption"])}</figcaption></figure></div>',
              f'<section class="profile-resources" aria-labelledby="short-bio-title"><h2 id="short-bio-title">{escape(copy["short_heading"])}</h2><p>{mixed(copy["short_bio"], lang)}</p></section>',
              f'<section class="profile-resources" aria-labelledby="extended-bio-title"><h2 id="extended-bio-title">{escape(copy["extended_heading"])}</h2>']
    parts.extend('<p>' + mixed(paragraph, lang) + '</p>' for paragraph in copy['extended_bio'])
    parts += ['</section>', f'<section class="profile-resources quick-facts" aria-labelledby="press-facts-title"><h2 id="press-facts-title">{escape(copy["facts_heading"])}</h2><dl class="quick-facts-list">']
    parts.extend(f'<div><dt>{mixed(fact["label"], lang)}</dt><dd>{mixed(fact["value"], lang)}</dd></div>' for fact in copy['facts'])
    parts += ['</dl></section>', f'<section class="profile-resources" id="press-resources" aria-labelledby="press-resources-title"><h2 id="press-resources-title">{escape(copy["resources_heading"])}</h2><p>{escape(copy["resources_intro"])}</p><div class="profile-downloads">']
    parts.extend(f'<a href="{resource["path"]}" download>{mixed(copy["resource_labels"][resource["id"]], lang)}</a>' for resource in data['resources'])
    parts += ['</div></section>', f'<section class="profile-resources" id="press-contact" aria-labelledby="press-contact-title"><h2 id="press-contact-title">{escape(copy["contact_heading"])}</h2><p>{escape(copy["contact_copy"])} <a href="mailto:{data["email"]}" dir="ltr">{data["email"]}</a>.</p></section>',
              f'<section class="profile-resources" aria-labelledby="press-context-title"><h2 id="press-context-title">{escape(copy["context_heading"])}</h2><ul>']
    parts.extend(f'<li><a href="{link["path"]}">{mixed(link["label"], lang)}</a></li>' for link in copy['context_links'])
    parts += ['</ul></section>',
              f'<footer class="editorial-footer"><nav aria-label="{escape(copy["context_heading"])}"><a href="{copy["context_links"][0]["path"]}">{escape(copy["footer_about"])}</a> · <a href="{copy["home_path"]}#contact">{escape(copy["footer_contact"])}</a></nav><p>{escape(copy["portrait_caption"])}</p></footer>',
              '</main>', '</body>', '</html>']
    return '\n'.join(parts) + '\n'


def main():
    check = '--check' in sys.argv
    data = json.loads((ROOT / 'locales/press.json').read_text())
    validate(data)
    changed = 0
    for lang in ('en', 'fa', 'ar'):
        path = ROOT / data['pages'][lang]['path'].lstrip('/')
        original = path.read_text() if path.exists() else None
        content = build(data, lang)
        if content == original:
            continue
        changed += 1
        print(('MISSING ' if check else 'Built ') + path.relative_to(ROOT).as_posix())
        if not check:
            if (path.read_text() if path.exists() else None) != original:
                raise RuntimeError(f'{path}: changed concurrently; preserve the other edit')
            path.write_text(content)
    if check and changed:
        raise SystemExit(1)
    print('PASS press pages: EN/FA/AR, approved English bios and existing public resources; '
          + ('no changes needed' if not changed else f'{changed} pages built'))


if __name__ == '__main__':
    main()
