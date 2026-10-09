"""Complete the social and search metadata on every page, in its own language.

Adds only what is missing, so it is safe to run again after pages change:
og:site_name, og:locale, og:locale:alternate (from the page's hreflang cluster), og:image:alt,
twitter:title, twitter:description, twitter:image, twitter:image:alt and a robots meta tag.
English is the original: each English page's main structured-data item names its Persian and
Arabic translations (workTranslation) and each translation names the English original
(translationOfWork). It also writes hreflang alternates into sitemap.xml from the same clusters.
Articles retain their image and identify it as the main image of their WebPage. Historical
article dates are preserved; new articles and changed dates must record the real publication
or update time as ISO 8601 with the publishing timezone (+03:30), never a guessed time.
Run with --check to report missing metadata or invalid article dates without changing files.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import html
import json
import re
import sys
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://a-samadi.com/'
LOCALES = {'en': 'en_US', 'fa': 'fa_IR', 'ar': 'ar_AE'}
SITE_NAME = 'Ahmadreza Samadi'
PORTRAIT_CARD = BASE + 'assets/img/ahmadreza-samadi-og.jpg'
PORTRAIT_ALT = {
    'en': 'Ahmadreza Samadi, Dubai-based founder and technical executive',
    'fa': 'تصویر احمدرضا صمدی',
    'ar': 'صورة أحمدرضا صمدي',
}
# Article cards carry their own illustration; describe what each one shows.
CARD_ALT = {
    'assets/writing/ai-confidence/og.png': {
        'en': 'It sounds sure. Is it right? A fictional AI answer about museum opening hours, checked against its source.',
        'fa': 'مطمئن به نظر می‌رسد؛ آیا درست است؟ یک پاسخ ساختگی هوش مصنوعی دربارهٔ ساعت کار موزه که با منبعش مقایسه شده است.',
        'ar': 'يبدو واثقًا، فهل هو صحيح؟ إجابة خيالية من ذكاء اصطناعي عن مواعيد متحف تمت مقارنتها بمصدرها.',
    },
    'assets/writing/charging-80/og.png': {
        'en': 'Why stop at 80%? A phone charging to 80% beside three reasons: a limit you chose, a learned routine and heat.',
        'fa': 'چرا شارژ روی ۸۰٪ می‌ایستد؟ گوشی در حال شارژ تا ۸۰٪ و سه دلیل: محدودیتی که خودتان انتخاب کرده‌اید، عادت آموخته‌شده و گرما.',
        'ar': 'لماذا يتوقف الشحن عند 80٪؟ هاتف يشحن حتى 80٪ بجانب ثلاثة أسباب: حدّ اخترته، وروتين مُتعلَّم، والحرارة.',
    },
    'assets/writing/cookie-consent/og.png': {
        'en': 'Accept cookies? A sketch of three websites, an ad company and the data one yes can share between them.',
        'fa': 'پذیرش کوکی‌ها؟ طرحی از سه وب‌سایت، یک شرکت تبلیغاتی و داده‌هایی که با یک «بله» میانشان به اشتراک گذاشته می‌شود.',
        'ar': 'قبول ملفات تعريف الارتباط؟ رسم لثلاثة مواقع وشركة إعلانات والبيانات التي قد تُشارَك بينها بموافقة واحدة.',
    },
    'assets/writing/satellite-messaging/satellite-messaging-og.png': {
        'en': 'A phone links to a satellite; title: How satellite messaging works',
        'fa': 'گوشی به ماهواره متصل می‌شود؛ عنوان: پیام‌رسانی ماهواره‌ای چگونه کار می‌کند',
        'ar': 'هاتف يتصل بقمر صناعي؛ العنوان: كيف تعمل الرسائل عبر الأقمار الصناعية',
    },
    'assets/writing/incognito/incognito-og.png': {
        'en': 'Incognito: who can still see? Illustrated private browser window.',
        'fa': 'حالت ناشناس: چه کسی هنوز می‌بیند؟ تصویری از پنجرهٔ مرور خصوصی.',
        'ar': 'التصفح المتخفي: من لا يزال يرى؟ رسم لنافذة تصفح خاصة.',
    },
    'assets/writing/profit-cash/cover.png': {
        'en': 'Profitable. Out of cash? A $3,000 profit on a $10,000 sale beside a $3,000 cash shortfall on payment day.',
        'fa': 'سودآور اما بدون نقدینگی؟ سود ۳٬۰۰۰ دلاری از فروشی ۱۰٬۰۰۰ دلاری در کنار کسری نقدی ۳٬۰۰۰ دلاری در روز پرداخت.',
        'ar': 'مربح لكن بلا سيولة؟ ربح 3,000 دولار من بيع بقيمة 10,000 دولار بجانب عجز نقدي 3,000 دولار يوم الدفع.',
    },
}
ROBOTS = 'index, follow, max-image-preview:large'
NOT_FOUND_DESCRIPTION = 'This page does not exist. Find Ahmadreza Samadi’s work, writing and contact details from the homepage.'

ARTICLE_TYPES = ('Article', 'NewsArticle', 'BlogPosting')
PUBLISHING_TIMEZONE = timezone(timedelta(hours=3, minutes=30))
# Frozen on 9 October 2026. These 20 existing articles in each language have dates whose
# historical time was not recorded. Only these exact values are grandfathered, so a new
# page or an updated legacy date cannot silently inherit a fabricated midnight timestamp.
LEGACY_ARTICLE_DATES = {
    'ai-agent-safety-boundaries.html': ('2026-09-29', '2026-09-29'),
    'ai-cost-per-verified-result.html': ('2026-09-24', '2026-09-25'),
    'ai-home-value-estimates.html': ('2026-10-03', '2026-10-03'),
    'ai-human-review-real-estate.html': ('2026-10-03', '2026-10-09'),
    'ai-rental-yield-cash-flow.html': ('2026-10-09', '2026-10-09'),
    'connected-ai-apps.html': ('2026-09-25', '2026-09-25'),
    'foldable-two-batteries.html': ('2026-10-03', '2026-10-03'),
    'how-satellite-messaging-works.html': ('2026-10-04', '2026-10-04'),
    'how-zip-files-work.html': ('2026-09-28', '2026-09-29'),
    'humanoid-robots-at-home.html': ('2026-10-03', '2026-10-03'),
    'incognito-private-browsing.html': ('2026-10-05', '2026-10-05'),
    'jev-ai-decision-model.html': ('2026-09-25', '2026-09-25'),
    'passkeys-face-id.html': ('2026-09-28', '2026-09-29'),
    'profitable-but-out-of-cash.html': ('2026-10-08', '2026-10-08'),
    'start-with-the-decision.html': ('2026-09-25', '2026-09-25'),
    'verify-ai-image-claims.html': ('2026-10-03', '2026-10-03'),
    'what-accept-cookies-means.html': ('2026-10-05', '2026-10-05'),
    'why-ai-sounds-confident.html': ('2026-10-05', '2026-10-05'),
    'why-full-storage-slows-computer.html': ('2026-10-09', '2026-10-09'),
    'why-phone-stops-charging-at-80.html': ('2026-10-05', '2026-10-05'),
}
LEGACY_ENGLISH_DECISION_DATES = ('2026-09-13T10:06:07+00:00', '2026-10-01')

META = r'<meta\s+(?:property|name)="{key}"\s+content="([^"]*)"\s*/?>'


def find(text, key):
    return re.search(META.format(key=re.escape(key)), text)


def value(text, key):
    match = find(text, key)
    return html.unescape(match[1]) if match else None


def insert_after(text, match, tag):
    """Insert a tag after an existing one, following that tag's own line and closing style."""
    end = match.end()
    raw = match[0]
    if raw.endswith('/>'):
        tag = tag[:-1].rstrip() + ' />'
    line_start = text.rfind('\n', 0, match.start()) + 1
    before = text[line_start:match.start()]
    if before.strip() == '':
        return text[:end] + '\n' + before + tag + text[end:]
    return text[:end] + tag + text[end:]


def meta(kind, key, content):
    return f'<meta {kind}="{key}" content="{html.escape(content, quote=True)}">'


def cluster(text):
    return {m[1]: m[2] for m in re.finditer(r'<link\s+rel="alternate"\s+hreflang="([^"]+)"\s+href="([^"]+)"', text)}


def language(text):
    match = re.search(r'<html[^>]*\slang="([a-z]{2})', text)
    return match[1] if match else 'en'


# The item a page is about, in order of preference, among the page's own structured-data nodes.
PAGE_TYPES = ('ProfilePage', 'AboutPage', 'CollectionPage', 'Article', 'NewsArticle', 'BlogPosting',
              'WebApplication', 'VideoObject', 'WebPage')
LD = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S)


def canonical(text):
    match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', text)
    return match[1] if match else None


def main_node(text):
    """Return (@id, node) for the page's own main item, or (None, None)."""
    url = canonical(text)
    if not url:
        return None, None
    best = None
    for block in LD.finditer(text):
        try:
            data = json.loads(block[2])
        except ValueError:
            continue
        nodes = data.get('@graph', [data]) if isinstance(data, dict) else []
        for node in nodes:
            kind = node.get('@type')
            kinds = [kind] if isinstance(kind, str) else list(kind or [])
            rank = min((PAGE_TYPES.index(k) for k in kinds if k in PAGE_TYPES), default=None)
            if rank is not None and str(node.get('@id', '')).startswith(url + '#'):
                if best is None or rank < best[0]:
                    best = (rank, node)
    return (best[1]['@id'], best[1]) if best else (None, None)


def page_for(url):
    relative = url.replace(BASE, '', 1)
    return ROOT / (relative + 'index.html' if relative == '' or relative.endswith('/') else relative)


def main_id(url):
    page = page_for(url)
    return main_node(page.read_text())[0] if page.is_file() else None


def article_node(text):
    own_id, node = main_node(text)
    if node:
        kind = node.get('@type')
        kinds = [kind] if isinstance(kind, str) else list(kind or [])
        if any(kind in ARTICLE_TYPES for kind in kinds):
            return own_id, node
    return None, None


def image_url(image):
    if isinstance(image, str):
        return image
    if isinstance(image, dict):
        return image.get('url') or image.get('contentUrl')
    if isinstance(image, list):
        return next((url for url in map(image_url, image) if url), None)
    return None


def article_page_image(text):
    """primaryImageOfPage describes a WebPage, not an Article; retain the Article's image."""
    own_id, node = article_node(text)
    if not own_id or not image_url(node.get('image')):
        return text, []
    page = node.get('mainEntityOfPage')
    if isinstance(page, dict) and 'primaryImageOfPage' in page:
        return text, []
    url = canonical(text)
    if page != url and not (isinstance(page, dict) and (page.get('@id') == url or page.get('url') == url)):
        return text, []
    webpage = dict(page) if isinstance(page, dict) else {'@type': 'WebPage', '@id': url}
    webpage.setdefault('@type', 'WebPage')
    webpage['primaryImageOfPage'] = {'@type': 'ImageObject', 'url': image_url(node['image'])}
    # Replace only this property value; keep the rest of each JSON-LD block and HTML intact.
    decoder = json.JSONDecoder()
    for block in LD.finditer(text):
        if own_id not in block[2]:
            continue
        for match in re.finditer(r'"mainEntityOfPage"\s*:\s*', block[2]):
            old, length = decoder.raw_decode(block[2][match.end():])
            if old != page:
                continue
            start = block.start(2) + match.end()
            updated = text[:start] + json.dumps(webpage, ensure_ascii=False) + text[start + length:]
            return updated, ['WebPage primaryImageOfPage']
    return text, []


def article_issues(path, text, now=None):
    """Validate real timestamps for new/changed dates while retaining exact historical dates."""
    _, node = article_node(text)
    if not node:
        return []
    issues = []
    relative = path.relative_to(ROOT).as_posix()
    known_path = any(relative == prefix + path.name for prefix in ('writing/', 'fa/writing/', 'ar/writing/'))
    legacy = LEGACY_ARTICLE_DATES.get(path.name) if known_path else None
    if relative == 'writing/start-with-the-decision.html':
        legacy = LEGACY_ENGLISH_DECISION_DATES
    now = now or datetime.now(timezone.utc)
    parsed = {}
    for index, key in enumerate(('datePublished', 'dateModified')):
        value = node.get(key)
        historical = legacy is not None and value == legacy[index]
        if not isinstance(value, str):
            issues.append(f'{key} must record the actual date and time')
            continue
        if historical and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            parsed[key] = date.fromisoformat(value)
            continue
        if not historical and not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\+03:30', value):
            issues.append(f'{key} must use a real ISO 8601 datetime with +03:30; do not invent historical times')
            continue
        try:
            instant = datetime.fromisoformat(value)
            if instant.tzinfo is None:
                raise ValueError('missing timezone')
            parsed[key] = instant.astimezone(PUBLISHING_TIMEZONE)
            if instant > now:
                issues.append(f'{key} cannot be in the future')
        except ValueError:
            issues.append(f'{key} is not a valid ISO 8601 datetime')
    if len(parsed) == 2:
        published, modified = parsed['datePublished'], parsed['dateModified']
        if not all(isinstance(value, datetime) for value in (published, modified)):
            published, modified = (value.date() if isinstance(value, datetime) else value for value in (published, modified))
        if modified < published:
            issues.append('dateModified cannot precede datePublished')
    page = node.get('mainEntityOfPage')
    if not isinstance(page, dict) or page.get('@type') != 'WebPage' or page.get('@id', page.get('url')) != canonical(text):
        issues.append('mainEntityOfPage must identify the canonical WebPage')
    elif image_url(page.get('primaryImageOfPage')) != image_url(node.get('image')):
        issues.append('WebPage primaryImageOfPage must match the existing Article image')
    return issues


def translation_links(text):
    """English pages list their translations; Persian and Arabic pages point to the English original."""
    head = text[:text.find('</head>')]
    lang = language(head)
    alternates = cluster(head)
    own_id, node = main_node(text)
    if not own_id or 'en' not in alternates:
        return text, []
    if lang == 'en':
        key = 'workTranslation'
        value = [{'@id': target} for target in (main_id(alternates[code]) for code in ('fa', 'ar') if code in alternates) if target]
    else:
        key = 'translationOfWork'
        original = main_id(alternates['en'])
        value = {'@id': original} if original else None
    if not value or key in node:
        return text, []
    anchor = f'"@id": "{own_id}"'
    at = text.find(anchor)
    if at < 0:
        return text, []
    end = at + len(anchor)
    entry = f'"{key}": ' + json.dumps(value, ensure_ascii=False)
    line_start = text.rfind('\n', 0, at) + 1
    indent = text[line_start:at]
    if indent.strip() == '' and text[end:end + 1] == ',' and text[end + 1:end + 2] == '\n':
        text = text[:end + 2] + indent + entry + ',\n' + text[end + 2:]
    else:
        text = text[:end] + ', ' + entry + text[end:]
    block = next(b for b in LD.finditer(text) if b.start() <= at < b.end())
    json.loads(block[2])
    return text, [key]


def enrich(path, text):
    head_end = text.find('</head>')
    if head_end < 0:
        return text, []
    head, rest = text[:head_end], text[head_end:]
    lang = language(head)
    added = []

    def add_after(anchor_keys, kind, key, content):
        nonlocal head
        if find(head, key) or content is None:
            return
        anchor = next((m for m in (find(head, k) for k in anchor_keys) if m), None)
        if not anchor:
            return
        head = insert_after(head, anchor, meta(kind, key, content))
        added.append(key)

    if path.name == '404.html':
        if not find(head, 'description'):
            title = re.search(r'</title>', head)
            if title:
                head = head[:title.end()] + meta('name', 'description', NOT_FOUND_DESCRIPTION) + head[title.end():]
                added.append('description')
        return head + rest, added

    if not find(head, 'og:title'):
        return text, []
    add_after(['og:type', 'og:title'], 'property', 'og:site_name', SITE_NAME)
    add_after(['og:site_name', 'og:type', 'og:url'], 'property', 'og:locale', LOCALES.get(lang, 'en_US'))
    if not find(head, 'og:locale:alternate'):
        others = [code for code in ('en', 'fa', 'ar') if code != lang and code in cluster(head)]
        anchor = find(head, 'og:locale')
        if not anchor:
            others = []
        for code in reversed(others):
            head = insert_after(head, anchor, meta('property', 'og:locale:alternate', LOCALES[code]))
        if others:
            added.append('og:locale:alternate')
    image = value(head, 'og:image')
    if image:
        card = image.replace(BASE, '')
        alt = PORTRAIT_ALT[lang] if image == PORTRAIT_CARD else CARD_ALT.get(card, {}).get(lang)
        add_after(['og:image:height', 'og:image:width', 'og:image:type', 'og:image'], 'property', 'og:image:alt', alt)
    add_after(['twitter:card'], 'name', 'twitter:title', value(head, 'og:title'))
    add_after(['twitter:title', 'twitter:card'], 'name', 'twitter:description', value(head, 'og:description'))
    add_after(['twitter:description', 'twitter:title', 'twitter:card'], 'name', 'twitter:image', value(head, 'og:image'))
    add_after(['twitter:image'], 'name', 'twitter:image:alt', value(head, 'og:image:alt'))
    add_after(['description'], 'name', 'robots', ROBOTS)
    # Persian and Arabic text is set in Vazirmatn; fetch it with the stylesheet instead of after layout.
    if re.search(r'<html[^>]*\sdir="rtl"', head) and not re.search(r'<link[^>]+rel="preload"[^>]+vazirmatn', head):
        sheet = re.search(r'<link\s+rel="stylesheet"[^>]*>', head)
        if sheet:
            line_start = head.rfind('\n', 0, sheet.start()) + 1
            before = head[line_start:sheet.start()]
            closing = ' />' if sheet[0].endswith('/>') else '>'
            preload = '<link rel="preload" as="font" type="font/woff2" href="/assets/fonts/vazirmatn-arabic-wght.woff2" crossorigin' + closing
            joiner = '\n' + before if before.strip() == '' else ''
            head = head[:sheet.start()] + preload + (joiner if joiner else '') + head[sheet.start():]
            added.append('font preload')
    text, linked = translation_links(head + rest)
    text, image_added = article_page_image(text)
    return text, added + linked + image_added


def sitemap(check):
    path = ROOT / 'sitemap.xml'
    namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    xhtml = 'http://www.w3.org/1999/xhtml'
    ElementTree.register_namespace('', namespace)
    ElementTree.register_namespace('image', 'http://www.google.com/schemas/sitemap-image/1.1')
    ElementTree.register_namespace('video', 'http://www.google.com/schemas/sitemap-video/1.1')
    ElementTree.register_namespace('xhtml', xhtml)
    tree = ElementTree.parse(path)
    order = {'en': 0, 'fa': 1, 'ar': 2, 'x-default': 3}
    added = 0
    for url in tree.getroot().findall(f'{{{namespace}}}url'):
        loc = url.find(f'{{{namespace}}}loc').text
        relative = loc.replace(BASE, '')
        page = ROOT / (relative + 'index.html' if relative == '' or relative.endswith('/') else relative)
        alternates = cluster(page.read_text()) if page.is_file() else {}
        present = {link.get('hreflang') for link in url.findall(f'{{{xhtml}}}link')}
        missing = sorted((code for code in alternates if code not in present), key=lambda code: order.get(code, 9))
        if not missing:
            continue
        added += len(missing)
        # Language links follow loc and lastmod, before any image entries.
        position = len([child for child in url if child.tag in (f'{{{namespace}}}loc', f'{{{namespace}}}lastmod', f'{{{namespace}}}changefreq', f'{{{namespace}}}priority', f'{{{xhtml}}}link')])
        for code in missing:
            link = ElementTree.Element(f'{{{xhtml}}}link', {'rel': 'alternate', 'hreflang': code, 'href': alternates[code]})
            url.insert(position, link)
            position += 1
    if added and not check:
        ElementTree.indent(tree, space='    ')
        tree.write(path, encoding='utf-8', xml_declaration=True)
        with path.open('a') as handle:
            handle.write('\n')
    return added


def main():
    check = '--check' in sys.argv
    changed = 0
    invalid = 0
    for path in sorted(ROOT.rglob('*.html')):
        relative = path.relative_to(ROOT)
        if relative.parts[0] in ('.git', 'node_modules') or path.name.startswith('google'):
            continue
        text = path.read_text()
        updated, added = enrich(path, text)
        if added:
            changed += 1
            print(('MISSING ' if check else 'Updated ') + relative.as_posix() + ': ' + ', '.join(added))
            if not check:
                path.write_text(updated)
        issues = article_issues(path, updated)
        if issues:
            invalid += 1
            print('INVALID ' + relative.as_posix() + ': ' + '; '.join(issues))
    links = sitemap(check)
    if links:
        print(('MISSING ' if check else 'Added ') + f'{links} sitemap hreflang links')
    if invalid or (check and (changed or links)):
        sys.exit(1)
    print('PASS metadata: ' + ('no changes needed' if not changed and not links else f'{changed} pages and {links} sitemap links updated'))


if __name__ == '__main__':
    main()
