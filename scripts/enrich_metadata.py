"""Complete the social and search metadata on every page, in its own language.

Adds only what is missing, so it is safe to run again after pages change:
og:site_name, og:locale, og:locale:alternate (from the page's hreflang cluster), og:image:alt,
twitter:title, twitter:description, twitter:image, twitter:image:alt and a robots meta tag.
It also writes hreflang alternates into sitemap.xml from the same clusters.
Run with --check to report missing metadata without changing files.
"""
from pathlib import Path
import html
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
    return head + rest, added


def sitemap(check):
    path = ROOT / 'sitemap.xml'
    namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    xhtml = 'http://www.w3.org/1999/xhtml'
    ElementTree.register_namespace('', namespace)
    ElementTree.register_namespace('image', 'http://www.google.com/schemas/sitemap-image/1.1')
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
    links = sitemap(check)
    if links:
        print(('MISSING ' if check else 'Added ') + f'{links} sitemap hreflang links')
    if check and (changed or links):
        sys.exit(1)
    print('PASS metadata: ' + ('no changes needed' if not changed and not links else f'{changed} pages and {links} sitemap links updated'))


if __name__ == '__main__':
    main()
