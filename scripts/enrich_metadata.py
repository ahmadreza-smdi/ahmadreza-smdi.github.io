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
Video publication dates must also be real ISO 8601 datetimes with an explicit timezone,
agree across pages showing the same film, and match the video sitemap publication date.
Run with --check to report missing metadata or invalid article/video dates without changing files.
"""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from check_internal_links import site_pages
from seo_document import Document
from urllib.parse import urljoin
import html
import json
import re
import sys
import struct
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
CONTENT_UPDATES = json.loads((ROOT / 'locales/content-updates.json').read_text())
DESCRIPTION_UPDATES = json.loads((ROOT / 'locales/metadata-descriptions.json').read_text())
SHARE_IMAGES = {row['source']: row['output'] for row in json.loads((ROOT / 'locales/share-images.json').read_text())['images']}
BASE = 'https://a-samadi.com/'
LOCALES = {'en': 'en_US', 'fa': 'fa_IR', 'ar': 'ar_AE'}
SITE_NAME = 'Ahmadreza Samadi'
PORTRAIT_CARD = BASE + 'assets/img/ahmadreza-samadi-og.jpg'
PORTRAIT_ALT = {
    'en': 'Ahmadreza Samadi, Dubai-based technology entrepreneur',
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
LEGACY_ENGLISH_DECISION_DATES = ('2026-09-13T13:36:07+03:30', '2026-10-01')

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


def schema_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from schema_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from schema_nodes(child)


def complete_schema(path, text, include_breadcrumb=True):
    """Fill source-supported entity links without changing historical dates."""
    url = canonical(text)
    if not url:
        return text, []
    lang = language(text)
    relative = path.relative_to(ROOT).as_posix()
    unlocalized = re.sub(r'^(fa|ar)/', '', relative)
    changes = []
    update_record = CONTENT_UPDATES.get(relative)
    description_record = DESCRIPTION_UPDATES.get(relative)
    own_id, _ = main_node(text)

    def update(match):
        data = json.loads(match[2])
        before = json.dumps(data, ensure_ascii=False)
        for node in schema_nodes(data):
            kind = node.get('@type')
            is_main_item = own_id is not None and kind is not None and node.get('@id') == own_id
            if update_record and is_main_item:
                node['dateModified'] = update_record['dateModified']
            if description_record and is_main_item and 'title' in description_record:
                node['name'] = description_record['title']
            if description_record and (is_main_item or node.get('description') == description_record['previous']):
                node['description'] = description_record['description']
            if kind in ARTICLE_TYPES and 'publisher' not in node:
                node['publisher'] = {'@id': BASE + '#person'}
            if (relative == 'writing/start-with-the-decision.html' and kind in ARTICLE_TYPES
                    and node.get('datePublished') == '2026-09-13T10:06:07+00:00'):
                node['datePublished'] = datetime.fromisoformat(node['datePublished']).astimezone(PUBLISHING_TIMEZONE).isoformat()
            if kind == 'ProfilePage' and unlocalized == 'index.html':
                node.setdefault('inLanguage', lang)
            if kind == 'WebApplication' and unlocalized.startswith('studies/rent-own-2026/'):
                node['author'] = {'@id': BASE + '#person'}
                node.setdefault('inLanguage', lang)
        if json.dumps(data, ensure_ascii=False) == before:
            return match[0]
        changes.append('structured-data completeness')
        return match[1] + json.dumps(data, ensure_ascii=False, indent=2) + match[3]

    text = LD.sub(update, text)
    nodes = [node for block in LD.finditer(text) for node in schema_nodes(json.loads(block[2]))]
    # Existing content pages and selected hubs; never invent parents or duplicate the hub.
    section = unlocalized.split('/')[0]
    hub = unlocalized in ('ideas.html', 'studies/index.html', 'work/index.html', 'carousels/index.html')
    if (not include_breadcrumb or (not hub and section not in ('writing', 'watch', 'work', 'studies', 'tools', 'carousels'))
            or (not hub and unlocalized == section + '/index.html')
            or 'noindex' in (value(text, 'robots') or '')
            or any(node.get('@type') == 'BreadcrumbList' for node in nodes)):
        return text, changes
    heading = re.search(r'<h1\b[^>]*>(.*?)</h1>', text, re.S)
    if not heading:
        return text, changes
    title = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', heading[1])).split())
    prefix = '' if lang == 'en' else lang + '/'
    labels = {
        'en': ('Home', {'writing': 'Writing', 'watch': 'Watch', 'work': 'Work', 'studies': 'Studies', 'tools': 'Tools', 'carousels': 'Carousels'}),
        'fa': ('خانه', {'writing': 'نوشته‌ها', 'watch': 'تماشا', 'work': 'کارها', 'studies': 'مطالعات', 'tools': 'ابزارها', 'carousels': 'اسلایدها'}),
        'ar': ('الرئيسية', {'writing': 'المقالات', 'watch': 'المشاهدة', 'work': 'الأعمال', 'studies': 'الدراسات', 'tools': 'الأدوات', 'carousels': 'الشرائح'}),
    }
    home, sections = labels[lang]
    trail = [(BASE + prefix, home)]
    parent = BASE + prefix + section + '/'
    if not hub and page_for(parent).is_file() and canonical(page_for(parent).read_text()) == parent:
        trail.append((parent, sections[section]))
    trail.append((url, title))
    breadcrumb = {'@context': 'https://schema.org', '@type': 'BreadcrumbList', '@id': url + '#breadcrumbs',
                  'itemListElement': [{'@type': 'ListItem', 'position': i, 'name': label, 'item': target}
                                      for i, (target, label) in enumerate(trail, 1)]}
    for block in LD.finditer(text):
        data = json.loads(block[2])
        if isinstance(data, dict) and '@graph' in data:
            breadcrumb.pop('@context')
            data['@graph'].append(breadcrumb)
            text = text[:block.start(2)] + json.dumps(data, ensure_ascii=False, indent=2) + text[block.end(2):]
            return text, changes + ['BreadcrumbList']
    text = text.replace('</head>', '<script type="application/ld+json">' + json.dumps(breadcrumb, ensure_ascii=False, indent=2) + '</script>\n</head>', 1)
    return text, changes + ['BreadcrumbList']


def local_image_dimensions(url):
    """Read intrinsic PNG, JPEG and SVG dimensions using the standard library."""
    if not url or not url.startswith(BASE):
        return None
    path = ROOT / url.removeprefix(BASE)
    if not path.is_file():
        return None
    if path.suffix.lower() == '.svg':
        root = ElementTree.parse(path).getroot()
        if root.tag == '{http://www.w3.org/2000/svg}svg':
            width, height = root.get('width', ''), root.get('height', '')
            if width.isdecimal() and height.isdecimal() and min(int(width), int(height)) > 0:
                return int(width), int(height)
        return None
    with path.open('rb') as handle:
        header = handle.read(24)
        if header.startswith(b'\x89PNG\r\n\x1a\n') and len(header) == 24:
            return struct.unpack('>II', header[16:24])
        if not header.startswith(b'\xff\xd8'):
            return None
        handle.seek(2)
        while True:
            marker = handle.read(1)
            if not marker:
                return None
            if marker != b'\xff':
                continue
            while marker == b'\xff':
                marker = handle.read(1)
            if marker in (b'', b'\xd9', b'\xda'):
                return None
            if marker == b'\x01' or b'\xd0' <= marker <= b'\xd8':
                continue
            length = handle.read(2)
            if len(length) != 2:
                return None
            length = int.from_bytes(length, 'big')
            if length < 2:
                return None
            if marker[0] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                frame = handle.read(5)
                if len(frame) != 5:
                    return None
                height, width = struct.unpack('>HH', frame[1:])
                return width, height
            handle.seek(length - 2, 1)


# These three films were released with their articles, without separate watch pages.
# Timestamps are the first successful native Pages deployments of their media blobs
# (cbcd50a and 399a508). Durations are measured from the actual MP4 containers.
ARTICLE_FILMS = {
    'where-wearable-ai-computation-runs': ('2026-10-16T23:53:42+03:30', 'PT39.958333S'),
    'virtual-machine-device-sharing-explained': ('2026-10-16T23:53:42+03:30', 'PT44.833008S'),
    'geospatial-ai-map-answer-review': ('2026-10-17T21:01:19+03:30', 'PT44.041667S'),
}


def describe_media(path, text):
    """Describe editorial images and known embedded films from the visible page."""
    doc = Document(text)
    url = canonical(text)
    if not url:
        return text
    own_id, article = article_node(text)
    media_id = own_id
    if not media_id and path.parent.name == 'rent-burden' and path.name == 'index.html':
        _, page = main_node(text)
        if page:
            media_id = page.get('mainEntity', {}).get('@id')
    images = []
    for image in doc.tags('img'):
        src = urljoin(url, image.get('src'))
        if not (src.startswith((BASE + 'assets/writing/', BASE + 'studies/rent-burden/')) and image.get('alt')):
            continue
        size = local_image_dimensions(src)
        if size:
            images.append({'@type': 'ImageObject', 'contentUrl': src, 'width': size[0],
                           'height': size[1], 'caption': image.get('alt')})
    film = None
    if article and path.stem in ARTICLE_FILMS and path.parent.name == 'writing':
        videos = doc.tags('video')
        sources = [e for e in doc.tags('source') if e.get('type') == 'video/mp4']
        if len(videos) != 1 or len(sources) != 1 or not videos[0].get('poster'):
            raise ValueError(f'{path}: reviewed article player or poster changed')
        uploaded, duration = ARTICLE_FILMS[path.stem]
        film = {'@type': 'VideoObject', '@id': url + '#film', 'name': article['headline'],
                'description': article['description'], 'inLanguage': language(text),
                'thumbnailUrl': urljoin(url, videos[0].get('poster')),
                'contentUrl': urljoin(url, sources[0].get('src')), 'uploadDate': uploaded,
                'duration': duration, 'isPartOf': {'@id': own_id}}

    def update(block):
        data = json.loads(block[2])
        before = json.dumps(data, ensure_ascii=False)
        for node in list(schema_nodes(data)):
            if node.get('@type') == 'ImageObject' and image_url(node):
                src = image_url(node)
                size = local_image_dimensions(src)
                if size:
                    node['contentUrl'] = src
                    node['width'], node['height'] = size
            if media_id and node.get('@id') == media_id and node.get('@type') in (*ARTICLE_TYPES, 'Dataset'):
                if images:
                    previous = node.get('associatedMedia', [])
                    previous = previous if isinstance(previous, list) else [previous]
                    covered = {image['contentUrl'] for image in images}
                    retained = [item for item in previous if image_url(item) not in covered]
                    node['associatedMedia'] = retained + images
                if film:
                    if 'video' in node and node['video'].get('@id') != film['@id']:
                        raise ValueError(f'{path}: conflicting video annotation')
                    node['video'] = film
        if json.dumps(data, ensure_ascii=False) == before:
            return block[0]
        raw = block[2]
        prefix = raw[:len(raw) - len(raw.lstrip())]
        suffix = raw[len(raw.rstrip()):]
        return block[1] + prefix + json.dumps(data, ensure_ascii=False, indent=2) + suffix + block[3]
    return LD.sub(update, text)


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


def video_nodes(text):
    """Find VideoObjects in standalone, graph, list or nested JSON-LD structures."""
    def walk(value):
        if isinstance(value, dict):
            kinds = value.get('@type')
            if kinds == 'VideoObject' or (isinstance(kinds, list) and 'VideoObject' in kinds):
                yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for block in LD.finditer(text):
        try:
            data = json.loads(block[2])
        except ValueError:
            continue
        yield from walk(data)


def video_datetime_issues(value, label='VideoObject uploadDate', now=None):
    """Reject incomplete, impossible, timezone-free and future video publication times."""
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', value):
        return [f'{label} must use a real ISO 8601 datetime with an explicit timezone']
    # fromisoformat normalizes overflowing offset minutes; reject them before parsing.
    if not value.endswith('Z') and (int(value[-5:-3]) >= 24 or int(value[-2:]) >= 60):
        return [f'{label} has an invalid timezone offset']
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return [f'{label} is not a valid ISO 8601 datetime']
    if instant > (now or datetime.now(timezone.utc)):
        return [f'{label} cannot be in the future']
    return []


def video_issues(text, now=None):
    return [issue for node in video_nodes(text)
            for issue in video_datetime_issues(node.get('uploadDate'), now=now)]


def video_collection_issues(records, sitemap_text):
    """The same public film must retain one publication instant everywhere it appears."""
    issues = []
    instants = {}
    for source, node in records:
        content = node.get('contentUrl')
        value = node.get('uploadDate')
        if not content or video_datetime_issues(value):
            continue
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if content in instants and instant != instants[content][0]:
            issues.append(f'{source}: VideoObject uploadDate differs from the same film in {instants[content][1]}')
        else:
            instants[content] = (instant, source)
    namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    video_ns = '{http://www.google.com/schemas/sitemap-video/1.1}'
    for entry in ElementTree.fromstring(sitemap_text).findall(f'{namespace}url'):
        source = entry.findtext(f'{namespace}loc')
        for video in entry.findall(f'{video_ns}video'):
            content = video.findtext(f'{video_ns}content_loc')
            value = video.findtext(f'{video_ns}publication_date')
            invalid = video_datetime_issues(value, 'video sitemap publication_date')
            issues.extend(f'{source}: {issue}' for issue in invalid)
            if invalid:
                continue
            instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if content not in instants:
                issues.append(f'{source}: video sitemap has no matching valid VideoObject publication date')
            elif instant != instants[content][0]:
                issues.append(f'{source}: video sitemap publication_date differs from VideoObject uploadDate')
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


TRAIL_LABELS = 'Breadcrumb|مسیر صفحه|مسار الصفحة|مسار التنقل'
TRAIL = re.compile(r'<(nav|span)\b[^>]*aria-label="(?:' + TRAIL_LABELS + r')"[^>]*>(.*?)</\1>', re.S)
TRAIL_LINK = re.compile(r'<a\b[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>', re.S)


def visible_trail(text, url):
    match = TRAIL.search(text)
    if not match or not url:
        return []
    def label(markup):
        return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', markup)).split())
    links = list(TRAIL_LINK.finditer(match[2]))
    items = [(label(a[2]), urljoin(url, html.unescape(a[1]))) for a in links]
    if links:
        current = label(match[2][links[-1].end():]).strip(' /·›»')
        if current:
            items.append((current, url))
    return [{'@type': 'ListItem', 'position': i, 'name': name, 'item': target}
            for i, (name, target) in enumerate(items, 1)]


@lru_cache(maxsize=4)
def film_metadata(root):
    """The dedicated watch page describes the English film, including on translated articles."""
    result = {}
    namespaces = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'v': 'http://www.google.com/schemas/sitemap-video/1.1'}
    sitemap_file = root / 'sitemap.xml'
    thumbnails = {}
    if sitemap_file.is_file():
        for entry in ElementTree.parse(sitemap_file).findall('s:url', namespaces):
            thumb = entry.findtext('v:video/v:thumbnail_loc', namespaces=namespaces)
            if thumb:
                thumbnails[entry.findtext('s:loc', namespaces=namespaces)] = thumb
    for path in sorted((root / 'watch').glob('*.html')):
        watch_text = path.read_text()
        watch_url = canonical(watch_text)
        for block in LD.finditer(watch_text):
            graph = json.loads(block[2])
            for node in graph.get('@graph', [graph]):
                if node.get('@type') == 'VideoObject' and node.get('@id'):
                    result[node['@id']] = {key: node[key] for key in ('name', 'description', 'thumbnailUrl',
                        'uploadDate', 'duration', 'inLanguage') if key in node}
                    record = DESCRIPTION_UPDATES.get(path.relative_to(root).as_posix(), {})
                    if 'description' in record:
                        result[node['@id']]['description'] = record['description']
                    if watch_url in thumbnails:
                        result[node['@id']]['thumbnailUrl'] = thumbnails[watch_url]
                    result[node['@id']]['mainEntityOfPage'] = {'@id': watch_url + '#webpage'}
    return result


def align_public_entities(path, text, trail):
    """Emit consistent public identities and represent only breadcrumbs displayed on this page."""
    url = canonical(text)
    if not url:
        return text
    person = {'@id': BASE + '#person'}
    website = {'@id': BASE + '#website'}
    def update(block):
        document = json.loads(block[2])
        original = json.dumps(document, ensure_ascii=False)
        if not trail:
            if document.get('@type') == 'BreadcrumbList':
                return ''
            if '@graph' in document:
                document['@graph'] = [node for node in document['@graph'] if node.get('@type') != 'BreadcrumbList']
        roots = document.get('@graph', [document])
        for node in schema_nodes(document):
            kind, identity = node.get('@type'), node.get('@id')
            if not trail and isinstance(node.get('breadcrumb'), dict):
                node.pop('breadcrumb')
            if kind == 'BreadcrumbList' and trail:
                node['itemListElement'] = trail
                node.setdefault('@id', url + '#breadcrumbs')
            elif kind == 'WebSite' and identity == website['@id']:
                node['publisher'] = person.copy()
                node['author'] = person.copy()
            elif kind == 'Person' and (identity == person['@id'] or
                    node.get('name') == 'Ahmadreza Samadi' and node.get('url') == BASE + 'about.html'):
                node['@id'] = person['@id']
                node['name'] = 'Ahmadreza Samadi'
                node['url'] = BASE + 'about.html'
                if 'mainEntityOfPage' in node:
                    node['mainEntityOfPage'] = {'@id': BASE + 'about.html#profile'}
                if 'worksFor' in node:
                    node['alternateName'] = ['Ahmad Samadi']
                    node['email'] = 'ahmadreza.smdi@gmail.com'
            elif kind == 'ImageObject' and identity == BASE + '#portrait':
                node['caption'] = 'Ahmadreza Samadi in a dark suit'
            elif kind == 'VideoObject' and identity in film_metadata(ROOT):
                node.update(film_metadata(ROOT)[identity])
                node['isPartOf'] = website.copy()
            elif kind in ARTICLE_TYPES:
                node['isPartOf'] = website.copy()
                node.setdefault('author', person.copy())
            elif kind in ('ProfilePage', 'CollectionPage', 'WebPage', 'WebApplication') and (
                    str(identity or '').startswith(BASE) or any(node is item for item in roots)):
                node['isPartOf'] = website.copy()
                if kind == 'WebApplication':
                    node.setdefault('author', person.copy())
                if kind == 'ProfilePage':
                    node.setdefault('mainEntity', person.copy())
                if trail and kind in ('WebPage', 'ProfilePage', 'CollectionPage'):
                    node['breadcrumb'] = {'@id': url + '#breadcrumbs'}
                image = node.get('primaryImageOfPage')
                if isinstance(image, dict) and image.get('url'):
                    size = local_image_dimensions(image['url'])
                    if size:
                        image['width'], image['height'] = size
            elif kind == 'Dataset' and str(identity or '').startswith(BASE):
                node['isPartOf'] = website.copy()
        if original == json.dumps(document, ensure_ascii=False):
            return block[0]
        raw = block[2]
        leading = raw[:len(raw) - len(raw.lstrip())]
        trailing = raw[len(raw.rstrip()):]
        return block[1] + leading + json.dumps(document, ensure_ascii=False, indent=2) + trailing + block[3]
    text = LD.sub(update, text)
    if path.parent == ROOT / 'watch':
        documents = [json.loads(block[2]) for block in LD.finditer(text)]
        films = [node for document in documents for node in document.get('@graph', [document])
                 if node.get('@type') == 'VideoObject']
        if films and not any(node.get('@type') == 'WebPage' for document in documents
                             for node in document.get('@graph', [document])):
            watch_page = {'@context': 'https://schema.org', '@type': 'WebPage', '@id': url + '#webpage',
                          'url': url, 'inLanguage': language(text), 'isPartOf': website,
                          'mainEntity': {'@id': films[0]['@id']}}
            if trail:
                watch_page['breadcrumb'] = {'@id': url + '#breadcrumbs'}
            text = text.replace('</head>', '<script type="application/ld+json">' + json.dumps(watch_page, ensure_ascii=False, indent=2) + '</script>\n</head>', 1)
    if path == ROOT / 'carousels/index.html':
        gallery = re.search(r'<!-- galleries:start -->(.*?)</ul>', text, re.S)
        if not gallery:
            raise ValueError('Missing published gallery entries')
        links = TRAIL_LINK.findall(gallery[1])
        entries = [{'@type': 'ListItem', 'position': i, 'name': html.unescape(title), 'url': urljoin(url, href)}
                   for i, (href, title) in enumerate(links, 1)]
        heading = re.search(r'<h1\b[^>]*>(.*?)</h1>', text, re.S)
        collection = {'@context': 'https://schema.org', '@type': 'CollectionPage', '@id': url + '#page',
                      'url': url, 'name': html.unescape(heading[1]), 'description': value(text, 'description'),
                      'inLanguage': 'en', 'isPartOf': website,
                      'author': person, 'mainEntity': {'@type': 'ItemList', '@id': url + '#list',
                      'numberOfItems': len(entries), 'itemListElement': entries}}
        script = '<script type="application/ld+json">' + json.dumps(collection, ensure_ascii=False, indent=2) + '</script>'
        existing = next((entry for entry in LD.finditer(text) if json.loads(entry[2]).get('@id') == url + '#page'), None)
        if existing:
            text = text[:existing.start()] + script + text[existing.end():]
        else:
            text = text.replace('</head>', script + '\n</head>', 1)
    return text


PUBLIC_CONTACT = re.compile(
    r'(?<!<!--email_off-->)(<a\b(?=[^>]*\bhref="mailto:ahmadreza\.smdi@gmail\.com")[^>]*>.*?</a>)',
    re.I | re.S,
)


def preserve_public_contact(text):
    """Keep the published personal contact usable without client-side JavaScript."""
    return PUBLIC_CONTACT.sub(r'<!--email_off-->\1<!--/email_off-->', text)


def enrich(path, text):
    head_end = text.find('</head>')
    if head_end < 0:
        return text, []
    head, rest = text[:head_end], text[head_end:]
    lang = language(head)
    contact = preserve_public_contact(rest)
    added = ['public contact link'] if contact != rest else []
    rest = contact
    relative = path.relative_to(ROOT).as_posix()
    def decode_content_image(match):
        tag = match[0]
        if 'decoding=' in tag or not re.search(r'\balt="[^"]+"', tag):
            return tag
        added.append('asynchronous image decoding')
        return tag.replace('<img ', '<img decoding="async" ', 1)

    rest = re.sub(r'<img\s+[^>]+>', decode_content_image, rest)
    if relative.startswith('watch/'):
        poster = re.search(r'<div class="film-wrap">\s*<video\b[^>]*\bposter="(/assets/[^"]+)"', rest)
        if poster and f'href="{poster[1]}"' not in head:
            head += f'<link rel="preload" as="image" href="{poster[1]}" fetchpriority="high">\n'
            added.append('preload the visible film poster')
    if relative.startswith('carousels/') and path.name != 'index.html':
        title = re.search(r'<title>(.*?)</title>', head, re.S)
        suffix = ' | Ahmadreza Samadi'
        if title and not html.unescape(title[1]).endswith(suffix):
            candidate = html.unescape(title[1]) + suffix
            if len(candidate) <= 65:
                head = head[:title.start(1)] + html.escape(candidate) + head[title.end(1):]
                added.append('carousel title attribution')
    description_record = DESCRIPTION_UPDATES.get(path.relative_to(ROOT).as_posix())
    if description_record:
        if 'title' in description_record:
            title = description_record['title']
            source = re.search(r'<title>([^<]+)</title>', head)
            if not source or html.unescape(source[1]) not in (description_record['previous_title'], description_record.get('source_title'), description_record.get('superseded_title'), title):
                raise ValueError(f'{path}: title source changed; review the explicit metadata copy')
            if not 0 < len(title) <= 65:
                raise ValueError(f'{path}: reviewed title must contain 1–65 characters')
            if html.unescape(source[1]) != title:
                head = head[:source.start(1)] + html.escape(title) + head[source.end(1):]
                added.append('title')
            for key in ('og:title', 'twitter:title'):
                match = find(head, key)
                if match and html.unescape(match[1]) != title:
                    head = head[:match.start(1)] + html.escape(title) + head[match.end(1):]
                    added.append(key)
        description = description_record['description']
        if not 120 <= len(description) <= 165:
            raise ValueError(f'{path}: reviewed description must contain 120–165 characters')
        if value(head, 'description') not in (description_record['previous'], description_record.get('source_description', description), description_record.get('superseded_description', description), description):
            raise ValueError(f'{path}: description source changed; review the explicit metadata copy')
        for key in ('description', 'og:description', 'twitter:description'):
            match = find(head, key)
            if match and html.unescape(match[1]) != description:
                head = head[:match.start(1)] + html.escape(description, quote=True) + head[match.end(1):]
                added.append(key)
    update_record = CONTENT_UPDATES.get(path.relative_to(ROOT).as_posix())
    if update_record:
        for key in ('og:updated_time', 'article:modified_time'):
            match = find(head, key)
            if match and html.unescape(match[1]) != update_record['dateModified']:
                head = head[:match.start(1)] + update_record['dateModified'] + head[match.end(1):]
                added.append(key)

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
        linked = align_public_entities(path, head + rest, visible_trail(rest, canonical(head)))
        return linked, ['public graph or contact'] if linked != text else []
    add_after(['og:title'], 'property', 'og:description', value(head, 'description'))
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
    default_card = PORTRAIT_CARD
    mapped = SHARE_IMAGES.get(image.removeprefix(BASE)) if image else None
    if (not mapped and local_image_dimensions(image) != (1200, 630)
            and 'noindex' not in (value(head, 'robots') or '')
            and local_image_dimensions(default_card) == (1200, 630)):
        default_alt = PORTRAIT_ALT[lang]
        replacements = {'og:image': default_card, 'twitter:image': default_card,
                        'og:image:width': '1200', 'og:image:height': '630',
                        'og:image:alt': default_alt, 'twitter:image:alt': default_alt}
        for key, content in replacements.items():
            match = find(head, key)
            if match:
                head = head[:match.start(1)] + html.escape(content, quote=True) + head[match.end(1):]
            elif key == 'og:image':
                add_after(['og:url', 'og:title'], 'property', key, content)
            elif key == 'og:image:alt':
                add_after(['og:image'], 'property', key, content)
        image = default_card
        added.append('use existing default 1200 by 630 share card')
    if image:
        landscape = SHARE_IMAGES.get(image.removeprefix(BASE))
        if landscape:
            for key in ('og:image', 'twitter:image'):
                match = find(head, key)
                if match:
                    head = head[:match.start(1)] + BASE + landscape + head[match.end(1):]
                    added.append(key + ' landscape cover')
            image = BASE + landscape
            dimensions = local_image_dimensions(image)
            if dimensions != (1200, 630):
                raise ValueError('Reviewed landscape cover is missing or has incorrect dimensions: ' + landscape)
            for key, dimension in zip(('og:image:width', 'og:image:height'), dimensions):
                match = find(head, key)
                if match:
                    head = head[:match.start(1)] + str(dimension) + head[match.end(1):]
        dimensions = local_image_dimensions(image)
        if dimensions:
            add_after(['og:image'], 'property', 'og:image:width', str(dimensions[0]))
            add_after(['og:image:width'], 'property', 'og:image:height', str(dimensions[1]))
        card = image.replace(BASE, '')
        alt = PORTRAIT_ALT[lang] if image == PORTRAIT_CARD else CARD_ALT.get(card, {}).get(lang)
        if not alt:
            alt = value(head, 'og:title')
        add_after(['og:image:height', 'og:image:width', 'og:image:type', 'og:image'], 'property', 'og:image:alt', alt)
    add_after(['twitter:card'], 'name', 'twitter:title', value(head, 'og:title'))
    add_after(['twitter:title', 'twitter:card'], 'name', 'twitter:description', value(head, 'og:description'))
    add_after(['twitter:description', 'twitter:title', 'twitter:card'], 'name', 'twitter:image', value(head, 'og:image'))
    add_after(['twitter:image'], 'name', 'twitter:image:alt', value(head, 'og:image:alt'))
    add_after(['description'], 'name', 'robots', ROBOTS)
    add_after(['robots', 'description'], 'name', 'referrer', 'strict-origin-when-cross-origin')
    if lang == 'en':
        for key in ('og:image:alt', 'twitter:image:alt'):
            old_alt = value(head, key)
            if old_alt and 'technical executive' in old_alt:
                match = find(head, key)
                head = head[:match.start(1)] + html.escape(old_alt.replace('founder and technical executive', 'technology entrepreneur').replace('technical executive', 'technology entrepreneur'), quote=True) + head[match.end(1):]
                added.append(key + ' identity wording')
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
    trail = visible_trail(rest, canonical(head))
    text, schema_added = complete_schema(path, text, include_breadcrumb=bool(trail))
    aligned = align_public_entities(path, text, trail)
    detailed = describe_media(path, aligned)
    return detailed, added + linked + image_added + schema_added + (['public entity links'] if aligned != text else []) + (['editorial media'] if detailed != aligned else [])


def sitemap(check):
    path = ROOT / 'sitemap.xml'
    namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    xhtml = 'http://www.w3.org/1999/xhtml'
    ElementTree.register_namespace('', namespace)
    ElementTree.register_namespace('image', 'http://www.google.com/schemas/sitemap-image/1.1')
    ElementTree.register_namespace('video', 'http://www.google.com/schemas/sitemap-video/1.1')
    ElementTree.register_namespace('xhtml', xhtml)
    tree = ElementTree.parse(path)
    image_ns = '{http://www.google.com/schemas/sitemap-image/1.1}'
    listed_images = {n.text for n in tree.iter(image_ns + 'loc')}
    html_images = set()
    for entry in tree.getroot().findall(f'{{{namespace}}}url'):
        entry_url = entry.findtext(f'{{{namespace}}}loc')
        source_page = page_for(entry_url)
        if not source_page.is_file():
            continue
        doc = Document(source_page.read_text())
        for tag in doc.elements:
            refs = []
            if tag.tag == 'img':
                refs.append(tag.get('src'))
            if tag.tag == 'video':
                refs.append(tag.get('poster'))
            if tag.tag == 'link' and tag.get('as') == 'image':
                refs.append(tag.get('href'))
            if tag.tag == 'meta' and (tag.get('property') == 'og:image' or tag.get('name') == 'twitter:image'):
                refs.append(tag.get('content'))
            if tag.tag in ('img', 'source'):
                refs.extend(item.split()[0] for item in tag.get('srcset').split(',') if item.strip())
            html_images.update(urljoin(entry_url, ref) for ref in refs if ref)
    order = {'en': 0, 'fa': 1, 'ar': 2, 'x-default': 3}
    added = 0
    for url in tree.getroot().findall(f'{{{namespace}}}url'):
        loc = url.find(f'{{{namespace}}}loc').text
        relative = loc.replace(BASE, '')
        page = ROOT / (relative + 'index.html' if relative == '' or relative.endswith('/') else relative)
        if page.is_file():
            source = page.read_text()
            _, node = main_node(source)
            if relative.startswith('writing/') and node and node.get('@type') in ARTICLE_TYPES:
                primary = image_url(node.get('image'))
                if (primary and primary.startswith(BASE + 'assets/share/') and
                        primary not in html_images and primary not in listed_images and local_image_dimensions(primary)):
                    image_entry = ElementTree.SubElement(url, image_ns + 'image')
                    ElementTree.SubElement(image_entry, image_ns + 'loc').text = primary
                    listed_images.add(primary)
                    added += 1
            if relative.startswith('writing/') and page.stem in ARTICLE_FILMS:
                film = next((f for f in video_nodes(source) if f.get('@id') == loc + '#film'), None)
                if film:
                    ns = '{http://www.google.com/schemas/sitemap-video/1.1}'
                    fields = {'thumbnail_loc': film['thumbnailUrl'], 'title': film['name'],
                              'description': film['description'], 'content_loc': film['contentUrl'],
                              'publication_date': film['uploadDate']}
                    entry = next((v for v in url.findall(ns + 'video')
                                  if v.findtext(ns + 'content_loc') == film['contentUrl']), None)
                    if entry is None:
                        entry = ElementTree.SubElement(url, ns + 'video')
                    for field, value in fields.items():
                        item = entry.find(ns + field)
                        if item is None:
                            item = ElementTree.SubElement(entry, ns + field)
                        if item.text != value:
                            item.text = value
                            added += 1
            modified = node.get('dateModified') if node else None
            # Reuse the page's recorded precision; never stamp the build time.
            if modified:
                lastmod = url.find(f'{{{namespace}}}lastmod')
                if lastmod is None:
                    lastmod = ElementTree.Element(f'{{{namespace}}}lastmod')
                    url.insert(1, lastmod)
                if lastmod.text != modified:
                    lastmod.text = modified
                    added += 1
        if loc == BASE:
            for key in ('changefreq', 'priority'):
                element = url.find(f'{{{namespace}}}{key}')
                if element is not None:
                    url.remove(element)
                    added += 1
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
    video_records = []
    for path in sorted(site_pages(ROOT)):
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
        issues = article_issues(path, updated) + video_issues(updated)
        video_records.extend((relative.as_posix(), node) for node in video_nodes(updated))
        if issues:
            invalid += 1
            print('INVALID ' + relative.as_posix() + ': ' + '; '.join(issues))
    video_problems = video_collection_issues(video_records, (ROOT / 'sitemap.xml').read_text())
    invalid += len(video_problems)
    for issue in video_problems:
        print('INVALID ' + issue)
    links = sitemap(check)
    if links:
        print(('MISSING ' if check else 'Updated ') + f'{links} sitemap metadata records')
    if invalid or (check and (changed or links)):
        sys.exit(1)
    print('PASS metadata: ' + ('no changes needed' if not changed and not links else f'{changed} pages and {links} sitemap records updated'))


if __name__ == '__main__':
    main()
