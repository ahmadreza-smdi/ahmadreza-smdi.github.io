"""Build or check the six curated topic hubs from their public locale data.

The reading destinations and their current headings come from existing pages.
These are CollectionPages, so they do not create articles or publication dates.
"""

import argparse
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "locales/topic-hubs.json"
BASE = "https://a-samadi.com/"
IMAGE = BASE + "assets/img/ahmadreza-samadi-og.jpg"
LOCALES = {"en": "en_US", "fa": "fa_IR", "ar": "ar_AE"}
LABELS = {
    "en": {
        "name": "Ahmadreza Samadi", "home": "Home", "writing": "Writing",
        "skip": "Skip to content", "breadcrumb": "Breadcrumb", "by": "By",
        "english": "Read the English original", "author": "About the author",
        "related": "Related pages", "all_writing": "All writing",
        "profiles": "Official profiles", "contact": "Get in touch →",
        "position": "Technology Entrepreneur", "next": "Continue reading",
        "image_alt": "Ahmadreza Samadi, Dubai-based founder and technical executive",
    },
    "fa": {
        "name": "احمدرضا صمدی", "home": "صفحه اصلی", "writing": "نوشته‌ها",
        "skip": "رفتن به محتوا", "breadcrumb": "مسیر صفحه", "by": "نوشته",
        "english": "مطالعه نسخه اصلی انگلیسی", "author": "درباره نویسنده",
        "related": "صفحه‌های مرتبط", "all_writing": "همه نوشته‌ها",
        "profiles": "صفحه‌های رسمی", "contact": "تماس ←",
        "position": "کارآفرین فناوری", "next": "ادامه مطالعه",
        "image_alt": "تصویر احمدرضا صمدی",
    },
    "ar": {
        "name": "أحمدرضا صمدي", "home": "الرئيسية", "writing": "المقالات",
        "skip": "انتقل إلى المحتوى", "breadcrumb": "مسار الصفحة", "by": "بقلم",
        "english": "اقرأ النسخة الإنجليزية الأصلية", "author": "عن الكاتب",
        "related": "صفحات ذات صلة", "all_writing": "جميع المقالات",
        "profiles": "الحسابات الرسمية", "contact": "تواصل معي ←",
        "position": "رائد أعمال تقني", "next": "تابع القراءة",
        "image_alt": "صورة أحمدرضا صمدي",
    },
}


class Heading(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.inside = False
        self.parts = []
        self.canonical = None
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "h1":
            self.inside = True
        if tag == "br" and self.inside:
            self.parts.append(" ")
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")

    def handle_endtag(self, tag):
        if tag == "h1":
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)

    @property
    def title(self):
        return " ".join("".join(self.parts).split())


def local_prefix(language):
    return "" if language == "en" else language + "/"


def resource(data, key, language):
    paths = data["resources"][key]["paths"]
    destination_language = language if language in paths else "en"
    relative = paths[destination_language]
    source = ROOT / relative
    if not source.is_file():
        raise ValueError(f"Missing reading destination: {relative}")
    metadata = Heading(source.read_text())
    if metadata.canonical != BASE + relative or not metadata.title:
        raise ValueError(f"Invalid reading destination: {relative}")
    return {"url": BASE + relative, "href": "/" + relative,
            "title": metadata.title, "language": destination_language}


def tagged_link(destination, key, label):
    language = ' hreflang="en"' if destination["language"] == "en" else ""
    return (f'<a href="{escape(destination["href"], quote=True)}"'
            f' data-topic-resource="{escape(key, quote=True)}"{language}>'
            f'{escape(label)}</a>')


def render(data, hub, language):
    copy = hub["locales"][language]
    labels = LABELS[language]
    prefix = local_prefix(language)
    canonical = BASE + hub["paths"][language]
    biography = BASE + prefix + "about.html"
    urls = {code: BASE + path for code, path in hub["paths"].items()}
    alternates = [f'<link rel="alternate" hreflang="{code}" href="{urls[code]}">'
                  for code in ("en", "fa", "ar")]
    alternates.append(f'<link rel="alternate" hreflang="x-default" href="{urls["en"]}">')
    rtl_head = ""
    if language != "en":
        rtl_head = ('<link rel="preload" as="font" type="font/woff2" '
                    'href="/assets/fonts/vazirmatn-arabic-wght.woff2" crossorigin>\n'
                    '<link rel="stylesheet" href="/css/rtl.css?v=20261009-lagoon4">\n')
    other_locales = "\n".join(
        f'<meta property="og:locale:alternate" content="{LOCALES[code]}">'
        for code in ("en", "fa", "ar") if code != language)

    destinations = {key: resource(data, key, language) for key in hub["ordered_resources"]}
    names = {copy["case_study"]["resource"]: copy["case_study"]["label"],
             copy["film"]["resource"]: copy["film"]["label"],
             copy["apply"]["resource"]: copy["apply"]["label"]}
    for card in copy["reading_path"]:
        names[card["resource"]] = destinations[card["resource"]]["title"]
    page = {
        "@type": "CollectionPage", "@id": canonical + "#page", "url": canonical,
        "name": copy["title"], "description": copy["description"], "inLanguage": language,
        "author": {"@type": "Person", "@id": BASE + "#person",
                   "name": "Ahmadreza Samadi", "url": biography},
        "about": [{"@id": BASE + "#person"},
                  {"@id": BASE + ("#appraiva" if hub["id"] == "ai-real-estate" else "#royal-abraj")}],
        "isPartOf": {"@id": BASE + "#website"},
        "image": {"@id": BASE + "#portrait"},
        "primaryImageOfPage": {"@id": BASE + "#portrait"},
        "mainEntity": {
            "@type": "ItemList", "@id": canonical + "#reading-path",
            "itemListOrder": "https://schema.org/ItemListOrderAscending",
            "numberOfItems": len(hub["ordered_resources"]),
            "itemListElement": [
                {"@type": "ListItem", "position": index,
                 "url": destinations[key]["url"], "name": names[key]}
                for index, key in enumerate(hub["ordered_resources"], 1)
            ],
        },
    }
    if language == "en":
        page["workTranslation"] = [{"@id": urls[code] + "#page"} for code in ("fa", "ar")]
    else:
        page["translationOfWork"] = {"@id": urls["en"] + "#page"}
    schema = {"@context": "https://schema.org", "@graph": [page, {
        "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": labels["home"], "item": BASE + prefix},
            {"@type": "ListItem", "position": 2, "name": labels["writing"], "item": BASE + prefix + "writing/"},
            {"@type": "ListItem", "position": 3, "name": copy["heading"], "item": canonical},
        ],
    }]}

    case = copy["case_study"]
    context = "\n".join(f'<p>{escape(paragraph)}</p>' for paragraph in copy["context"])
    questions = "\n".join(f'<li>{escape(question)}</li>' for question in copy["questions"])
    cards = []
    numerals = "0123456789" if language == "en" else ("۰۱۲۳۴۵۶۷۸۹" if language == "fa" else "٠١٢٣٤٥٦٧٨٩")
    for index, card in enumerate(copy["reading_path"], 1):
        key = card["resource"]
        number = str(index).translate(str.maketrans("0123456789", numerals))
        cards.append(f'''<article aria-labelledby="resource-{key}">
<p class="eyebrow">{number} · {escape(card["question"])}</p>
<h2 id="resource-{key}">{tagged_link(destinations[key], key, destinations[key]["title"])}</h2>
<p>{escape(card["summary"])}</p>
</article>''')
    film = copy["film"]
    apply = copy["apply"]
    other_hub = next(item for item in data["hubs"] if item["id"] == copy["cross_hub"]["hub"])
    cross = copy["cross_hub"]
    original_link = ""
    if language != "en":
        original_link = (f'<p class="byline"><a href="/{hub["paths"]["en"]}" '
                         f'hreflang="en" data-locale-primary="en">{escape(labels["english"])}</a></p>\n')
    direction = '' if language == "en" else ' dir="rtl"'
    body_class = "editorial-body topic-hub" + (" persian-page" if language == "fa" else " arabic-page" if language == "ar" else "")
    return f'''<!doctype html>
<html lang="{language}"{direction}>
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="author" content="Ahmadreza Samadi">
<title>{escape(copy["title"])}</title>
<meta name="description" content="{escape(copy["description"], quote=True)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{canonical}">
{chr(10).join(alternates)}
<link rel="alternate" type="application/rss+xml" title="Ahmadreza Samadi — English writing" href="https://a-samadi.com/writing/feed.xml">
<link rel="icon" type="image/svg+xml" href="/assets/brand/favicon.svg">
{rtl_head}<link rel="stylesheet" href="/css/site.css?v=20261009-writing1">
<link rel="stylesheet" href="/css/author-box.css?v=20261009-author1">
<meta property="og:type" content="website"><meta property="og:site_name" content="Ahmadreza Samadi">
<meta property="og:title" content="{escape(copy["title"], quote=True)}">
<meta property="og:description" content="{escape(copy["description"], quote=True)}">
<meta property="og:url" content="{canonical}"><meta property="og:locale" content="{LOCALES[language]}">
{other_locales}
<meta property="og:image" content="{IMAGE}"><meta property="og:image:alt" content="{escape(labels["image_alt"], quote=True)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{escape(copy["title"], quote=True)}">
<meta name="twitter:description" content="{escape(copy["description"], quote=True)}">
<meta name="twitter:image" content="{IMAGE}"><meta name="twitter:image:alt" content="{escape(labels["image_alt"], quote=True)}">
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>
<script src="/js/site-analytics.js?v=20261009-analytics1" defer></script>
</head>
<body class="{body_class}">
<a class="skip-link" href="#main">{escape(labels["skip"])}</a>
<header class="editorial-header"><a href="/{prefix}"><img src="/assets/brand/ahmadreza-samadi-mark-azure.svg" alt="" width="44" height="28">{escape(labels["name"])} / {escape(labels["home"])}</a></header>
<main id="main" class="editorial">
<nav class="byline" aria-label="{escape(labels["breadcrumb"], quote=True)}"><a href="/{prefix}">{escape(labels["home"])}</a> / <a href="/{prefix}writing/">{escape(labels["writing"])}</a> / <span aria-current="page">{escape(copy["heading"])}</span></nav>
<p class="eyebrow">{escape(copy["eyebrow"])}</p>
<h1>{escape(copy["heading"])}</h1>
<p class="lead">{escape(copy["lead"])}</p>
<p class="byline">{escape(labels["by"])} <a rel="author" href="/{prefix}about.html">{escape(labels["name"])}</a></p>
{original_link}<section aria-labelledby="topic-context-heading">
<h2 id="topic-context-heading">{escape(copy["context_heading"])}</h2>
{context}
<p>{tagged_link(destinations[case["resource"]], case["resource"], case["label"])}: {escape(case["summary"])}</p>
</section>
<nav aria-labelledby="topic-questions-heading">
<h2 id="topic-questions-heading">{escape(copy["questions_heading"])}</h2>
<ul>{questions}</ul>
</nav>
<h2 id="reading-path">{escape(copy["reading_heading"])}</h2>
{chr(10).join(cards)}
<section aria-labelledby="topic-film-heading">
<h2 id="topic-film-heading">{escape(film["heading"])}</h2>
<p>{escape(film["summary"])}</p>
<p>{tagged_link(destinations[film["resource"]], film["resource"], film["label"])}</p>
</section>
<section aria-labelledby="topic-apply-heading">
<h2 id="topic-apply-heading">{escape(apply["heading"])}</h2>
<p>{escape(apply["summary"])}</p>
<p>{tagged_link(destinations[apply["resource"]], apply["resource"], apply["label"])}</p>
</section>
<section aria-labelledby="topic-next-heading">
<h2 id="topic-next-heading">{escape(labels["next"])}</h2>
<p><a href="/{other_hub["paths"][language]}">{escape(cross["label"])}</a>: {escape(cross["summary"])}</p>
</section>
<aside class="article-author" aria-labelledby="article-author-title">
<h2 id="article-author-title">{escape(labels["author"])}</h2>
<p class="article-author__name"><a href="/{prefix}about.html" rel="author">{escape(labels["name"])}</a></p>
<p>{escape(copy["author_bio"])}</p>
</aside>
<footer class="editorial-footer"><nav aria-label="{escape(labels["related"], quote=True)}"><a href="/{prefix}writing/">{escape(labels["all_writing"])}</a> · <a href="/{prefix}about.html#official-profiles">{escape(labels["profiles"])}</a></nav><p>{escape(labels["name"])} · {escape(labels["position"])}</p><a href="/{prefix}#contact">{escape(labels["contact"])}</a></footer>
</main>
</body>
</html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.loads(DATA.read_text())
    if data.get("primary_language") != "en":
        raise ValueError("Topic hubs must retain English as the original")
    pages = []
    for hub in data["hubs"]:
        if set(hub["paths"]) != {"en", "fa", "ar"} or set(hub["locales"]) != {"en", "fa", "ar"}:
            raise ValueError(f"Missing locale: {hub['id']}")
        for language in ("en", "fa", "ar"):
            path = ROOT / hub["paths"][language]
            expected_prefix = local_prefix(language) + "topics/"
            if not hub["paths"][language].startswith(expected_prefix) or path.suffix != ".html":
                raise ValueError(f"Unexpected generated path: {path}")
            current = path.read_text() if path.exists() else None
            pages.append((path, current, render(data, hub, language)))
    changed = [(path, current, expected) for path, current, expected in pages if current != expected]
    if args.check:
        for path, _, _ in changed:
            print(f"STALE {path.relative_to(ROOT)}")
        if changed:
            raise SystemExit(1)
        print(f"PASS topic hubs: {len(pages)} generated pages match their locale data and current reading destinations")
        return
    # Back up changed, existing outputs outside the public repository before replacing them.
    existing = [(path, current) for path, current, _ in changed if current is not None]
    if existing:
        backup = ROOT.parent.parent / "Backups" / ("topic-hubs-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        for path, current in existing:
            saved = backup / path.relative_to(ROOT)
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_text(current)
            if saved.read_text() != current:
                raise RuntimeError(f"Failed backup: {saved}")
        print(f"Backed up {len(existing)} changed pages to {backup}")
    for path, current, expected in changed:
        if (path.read_text() if path.exists() else None) != current:
            raise RuntimeError(f"Concurrent edit: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected)
        print(f"Built {path.relative_to(ROOT)}")
    print(f"PASS topic hubs: {len(pages)} pages, {len(changed)} written")


if __name__ == "__main__":
    main()
