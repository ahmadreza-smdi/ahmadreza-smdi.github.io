"""Build the English-first Now and Speaking pages from reviewed locale copy.

Update locales/status-pages.json when the public work snapshot or topic copy changes,
using the actual update instant with +03:30. Keep historical work and unpublished plans
out of Now, and do not imply past talks or confirmed availability on Speaking. This
builder writes only its six pages; it never advances dates automatically. Run --check
to verify generated pages, local destinations and their existing sitemap entries.
"""

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
import re
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "locales/status-pages.json"
BASE = "https://a-samadi.com/"
ZONE = timezone(timedelta(hours=3, minutes=30))
IMAGE = BASE + "assets/img/ahmadreza-samadi-og.jpg"
LANGUAGES = ("en", "fa", "ar")
LOCALES = {"en": "en_US", "fa": "fa_IR", "ar": "ar_AE"}
LABELS = {
    "en": {"name": "Ahmadreza Samadi", "home": "Home", "skip": "Skip to content",
           "updated": "Updated", "related": "Related pages", "position": "Technology Entrepreneur",
           "image_alt": "Ahmadreza Samadi, Dubai-based founder and technical executive"},
    "fa": {"name": "احمدرضا صمدی", "home": "صفحه اصلی", "skip": "رفتن به محتوا",
           "updated": "به‌روزرسانی", "related": "صفحه‌های مرتبط", "position": "کارآفرین فناوری",
           "image_alt": "تصویر احمدرضا صمدی"},
    "ar": {"name": "أحمدرضا صمدي", "home": "الرئيسية", "skip": "انتقل إلى المحتوى",
           "updated": "آخر تحديث", "related": "صفحات ذات صلة", "position": "رائد أعمال تقني",
           "image_alt": "صورة أحمدرضا صمدي"},
}
MONTHS = {
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"),
    "fa": ("ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن", "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"),
    "ar": ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"),
}


def prefix(language):
    return "" if language == "en" else language + "/"


def route(page_id, language):
    return prefix(language) + page_id + ".html"


def mixed(text, language):
    result = escape(text)
    if language != "en":
        for term in ("Appraiva", "USB-C"):
            result = result.replace(term, f'<bdi lang="en">{term}</bdi>')
    return result


def display_date(instant, language):
    value = f"{instant.day} {MONTHS[language][instant.month - 1]} {instant.year}"
    numerals = {"en": "0123456789", "fa": "۰۱۲۳۴۵۶۷۸۹", "ar": "٠١٢٣٤٥٦٧٨٩"}[language]
    return value.translate(str.maketrans("0123456789", numerals))


def link(item, language):
    return f'<a href="/{prefix(language)}{item["path"]}">{mixed(item["label"], language)}</a>'


def validate(data):
    if data["primary_language"] != "en" or data["email"] != "ahmadreza.smdi@gmail.com":
        raise ValueError("Status pages must remain English-first and use the personal email")
    if [page["id"] for page in data["pages"]] != ["now", "speaking"]:
        raise ValueError("This builder owns only Now and Speaking")
    generated = {route(page["id"], language) for page in data["pages"] for language in LANGUAGES}
    for page in data["pages"]:
        value = page["updated_at"]
        instant = datetime.fromisoformat(value)
        if (instant.utcoffset() != ZONE.utcoffset(None)
                or instant.isoformat(timespec="seconds") != value
                or instant > datetime.now(ZONE)):
            raise ValueError(f'{page["id"]}: use the actual update time as YYYY-MM-DDTHH:MM:SS+03:30')
        if set(page["locales"]) != set(LANGUAGES):
            raise ValueError(f'{page["id"]}: EN/FA/AR copy is required')
        expected_sections = [section["id"] for section in page["locales"]["en"]["sections"]]
        if page["id"] == "now" and expected_sections[:2] != ["appraiva", "royal-abraj"]:
            raise ValueError("Now must retain Appraiva first and Royal Abraj second")
        expected_links = [item["path"] for section in page["locales"]["en"]["sections"] for item in section["links"]]
        for language, copy in page["locales"].items():
            sections = copy["sections"]
            if [section["id"] for section in sections] != expected_sections or len(set(expected_sections)) != len(sections):
                raise ValueError(f'{page["id"]}/{language}: section order must match the English original')
            if [item["path"] for section in sections for item in section["links"]] != expected_links:
                raise ValueError(f'{page["id"]}/{language}: reading destinations must match the English original')
            for section in sections:
                if not re.fullmatch(r"[a-z0-9-]+", section["id"]):
                    raise ValueError("Invalid section identifier")
            links = [item for section in sections for item in section["links"]] + copy["footer_links"]
            for item in links:
                relative = item["path"]
                if not re.fullmatch(r"[a-z0-9/-]+(?:\.html)?", relative) or relative.startswith("/") or ".." in relative:
                    raise ValueError(f"Invalid local destination: {relative}")
                target = prefix(language) + relative
                source = ROOT / (target + "index.html" if target.endswith("/") else target)
                if target not in generated and not source.is_file():
                    raise ValueError(f"Missing local destination: {target}")


def render(data, page, language):
    copy = page["locales"][language]
    labels = LABELS[language]
    canonical = BASE + route(page["id"], language)
    urls = {code: BASE + route(page["id"], code) for code in LANGUAGES}
    instant = datetime.fromisoformat(page["updated_at"])
    page_schema = {
        "@type": "WebPage", "@id": canonical + "#page", "url": canonical,
        "name": copy["title"], "description": copy["description"], "inLanguage": language,
        "dateModified": page["updated_at"],
        "author": {"@type": "Person", "@id": BASE + "#person", "name": "Ahmadreza Samadi", "url": BASE + "about.html"},
        "about": {"@id": BASE + "#person"}, "isPartOf": {"@id": BASE + "#website"},
        "image": {"@id": BASE + "#portrait"}, "primaryImageOfPage": {"@id": BASE + "#portrait"},
        "breadcrumb": {"@id": canonical + "#breadcrumbs"},
    }
    if language == "en":
        page_schema["workTranslation"] = [{"@id": urls[code] + "#page"} for code in ("fa", "ar")]
    else:
        page_schema["translationOfWork"] = {"@id": urls["en"] + "#page"}
    schema = {"@context": "https://schema.org", "@graph": [page_schema, {
        "@type": "BreadcrumbList", "@id": canonical + "#breadcrumbs",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": labels["home"], "item": BASE + prefix(language)},
            {"@type": "ListItem", "position": 2, "name": copy["heading"], "item": canonical},
        ],
    }]}
    direction = '' if language == "en" else ' dir="rtl"'
    body_class = "editorial-body" + (" persian-page" if language == "fa" else " arabic-page" if language == "ar" else "")
    parts = ["<!doctype html>", f'<html lang="{language}"{direction}>', "<head>",
             '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta name="author" content="Ahmadreza Samadi">',
             f'<title>{escape(copy["title"])}</title>',
             f'<meta name="description" content="{escape(copy["description"], quote=True)}">',
             '<meta name="robots" content="index, follow, max-image-preview:large">',
             f'<link rel="canonical" href="{canonical}">']
    parts.extend(f'<link rel="alternate" hreflang="{code}" href="{urls[code]}">' for code in LANGUAGES)
    parts += [f'<link rel="alternate" hreflang="x-default" href="{urls["en"]}">',
              '<link rel="icon" type="image/svg+xml" href="/assets/brand/favicon.svg">',
              '<link rel="stylesheet" href="/css/site.css?v=20261009-writing1">']
    if language != "en":
        parts += ['<link rel="preload" as="font" type="font/woff2" href="/assets/fonts/vazirmatn-arabic-wght.woff2" crossorigin>',
                  '<link rel="stylesheet" href="/css/rtl.css?v=20261009-lagoon4">']
    parts += ['<meta property="og:type" content="website">',
              '<meta property="og:site_name" content="Ahmadreza Samadi">',
              f'<meta property="og:title" content="{escape(copy["title"], quote=True)}">',
              f'<meta property="og:description" content="{escape(copy["description"], quote=True)}">',
              f'<meta property="og:url" content="{canonical}">',
              f'<meta property="og:locale" content="{LOCALES[language]}">']
    parts.extend(f'<meta property="og:locale:alternate" content="{LOCALES[code]}">' for code in LANGUAGES if code != language)
    parts += [f'<meta property="og:image" content="{IMAGE}">',
              f'<meta property="og:image:alt" content="{escape(labels["image_alt"], quote=True)}">',
              '<meta name="twitter:card" content="summary_large_image">',
              f'<meta name="twitter:title" content="{escape(copy["title"], quote=True)}">',
              f'<meta name="twitter:description" content="{escape(copy["description"], quote=True)}">',
              f'<meta name="twitter:image" content="{IMAGE}">',
              f'<meta name="twitter:image:alt" content="{escape(labels["image_alt"], quote=True)}">',
              '<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=False, indent=2) + '</script>',
              '<script src="/js/site-analytics.js?v=20261009-analytics1" defer></script>',
              '</head>', f'<body class="{body_class}">',
              f'<a class="skip-link" href="#main">{escape(labels["skip"])}</a>',
              f'<header class="editorial-header"><a href="/{prefix(language)}"><img src="/assets/brand/ahmadreza-samadi-mark-azure.svg" alt="" width="44" height="28">{escape(labels["name"])} / {escape(labels["home"])}</a></header>',
              '<main id="main" class="editorial">',
              f'<p class="eyebrow">{escape(labels["name"])}</p>',
              f'<h1>{escape(copy["heading"])}</h1>', f'<p class="lead">{mixed(copy["lead"], language)}</p>',
              f'<p class="byline">{escape(labels["updated"])} <time datetime="{page["updated_at"]}">{display_date(instant, language)}</time></p>']
    for section in copy["sections"]:
        parts += [f'<section aria-labelledby="{section["id"]}">',
                  f'<h2 id="{section["id"]}">{mixed(section["heading"], language)}</h2>']
        parts.extend(f'<p>{mixed(paragraph, language)}</p>' for paragraph in section["paragraphs"])
        if len(section["links"]) == 1:
            parts.append('<p>' + link(section["links"][0], language) + '</p>')
        else:
            parts.append('<ul>' + ''.join('<li>' + link(item, language) + '</li>' for item in section["links"]) + '</ul>')
        parts.append('</section>')
    if copy.get("contact_copy"):
        parts += ['<section aria-labelledby="enquiries">',
                  f'<h2 id="enquiries">{escape(copy["contact_heading"])}</h2>',
                  f'<p>{escape(copy["contact_copy"])} <a href="mailto:{data["email"]}" dir="ltr">{data["email"]}</a>.</p>',
                  '</section>']
    parts += ['<footer class="editorial-footer">',
              f'<nav aria-label="{escape(labels["related"])}">' + ' · '.join(link(item, language) for item in copy["footer_links"]) + '</nav>',
              f'<p>{escape(labels["name"])} · {escape(labels["position"])}</p>',
              '</footer>', '</main>', '</body>', '</html>']
    return '\n'.join(parts) + '\n'


def check_sitemap(data):
    namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    xhtml = '{http://www.w3.org/1999/xhtml}'
    entries = ElementTree.parse(ROOT / 'sitemap.xml').getroot().findall(namespace + 'url')
    for page in data['pages']:
        expected = {code: BASE + route(page['id'], code) for code in LANGUAGES}
        expected['x-default'] = expected['en']
        for language in LANGUAGES:
            matches = [entry for entry in entries if entry.findtext(namespace + 'loc') == expected[language]]
            if len(matches) != 1 or matches[0].findtext(namespace + 'lastmod') != page['updated_at']:
                raise ValueError(f'{expected[language]}: sitemap must match the actual page update time')
            alternates = matches[0].findall(xhtml + 'link')
            if len(alternates) != 4 or {item.get('hreflang'): item.get('href') for item in alternates} != expected:
                raise ValueError(f'{expected[language]}: sitemap alternates must match EN/FA/AR and English x-default')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify pages and sitemap without writing')
    args = parser.parse_args()
    original_data = DATA.read_text()
    data = json.loads(original_data)
    validate(data)
    outputs = []
    for page in data['pages']:
        for language in LANGUAGES:
            path = ROOT / route(page['id'], language)
            current = path.read_text() if path.exists() else None
            outputs.append((path, current, render(data, page, language)))
    changed = [(path, current, expected) for path, current, expected in outputs if current != expected]
    if args.check:
        check_sitemap(data)
        for path, _, _ in changed:
            print(f'STALE {path.relative_to(ROOT)}')
        if changed:
            raise SystemExit(1)
        print('PASS status pages: six EN/FA/AR pages match locale copy, local destinations and sitemap dates/alternates')
        return
    existing = [(path, current) for path, current, _ in changed if current is not None]
    if existing:
        backup = ROOT.parent.parent / 'Backups' / ('status-pages-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        for path, current in existing:
            saved = backup / path.relative_to(ROOT)
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_text(current)
            if saved.read_text() != current:
                raise RuntimeError(f'Failed backup: {saved}')
        print(f'Backed up {len(existing)} existing pages to {backup}')
    if DATA.read_text() != original_data:
        raise RuntimeError('Locale copy changed concurrently; re-read before building')
    for path, current, expected in changed:
        if (path.read_text() if path.exists() else None) != current:
            raise RuntimeError(f'Concurrent edit: {path}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected)
        print(f'Built {path.relative_to(ROOT)}')
    print(f'PASS status pages: {len(outputs)} pages, {len(changed)} written; update/check sitemap before release')


if __name__ == '__main__':
    main()
