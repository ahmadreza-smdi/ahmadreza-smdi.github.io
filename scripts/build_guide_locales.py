"""Generate complete RTL guide pages and behavior from the English originals."""
import json
import re
import sys
import subprocess
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from follow_blocks import enrich_follow
from enrich_metadata import enrich  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
html = (ROOT / 'tools/before-you-build-ai.html').read_text()
html = re.sub(r'<!-- follow-subscribe:start -->.*?<!-- follow-subscribe:end -->\n?', '', html, flags=re.S)
script = (ROOT / 'js/decision-guide.js').read_text()
for lang in ('fa', 'ar'):
    data = json.loads((ROOT / f'locales/decision-guide-{lang}.json').read_text())
    found = set()
    def text(match):
        value = match.group(1)
        if value in data['text']:
            found.add(value)
            return '>' + data['text'][value] + '<'
        return match.group(0)
    page = re.sub(r'>([^<>]+)<', text, html)
    assert found == set(data['text']), f'{lang}: source text changed; update translations'
    js = script
    for source, target in data['dynamic'].items():
        assert "'" + source + "'" in js, source
        assert "'" not in target, 'Escape apostrophes before generating JavaScript'
        js = js.replace("'" + source + "'", "'" + target + "'")
    for source, target in sorted(data['extra'].items(), key=lambda pair: -len(pair[0])):
        assert source in page or source in js, source
        page = page.replace(source, target)
        js = js.replace(source, target)
    page = page.replace('<html lang="en">', f'<html lang="{lang}" dir="rtl">')
    # The English guide lists its translations; a translation instead names the English original (added by enrich).
    page = re.sub(r'\n[ \t]*"workTranslation": \[[^\]]*\],', '', page)
    page = page.replace('"inLanguage": "en"', f'"inLanguage": "{lang}"')
    # Preserve shared assets; localize only document routes, not the canonical Person identity.
    page = page.replace('="../css/', '="../../css/').replace('="../assets/', '="../../assets/')
    page = re.sub(r'\.\./js/decision-guide\.js(\?[^" ]*)?', lambda match: f'../../js/decision-guide-{lang}.js' + (match.group(1) or ''), page)
    page = page.replace('href="/"', f'href="/{lang}/"')
    # Hreflang must remain reciprocal, so temporarily protect those complete tags.
    alternates = re.findall(r'<link rel="alternate"[^>]+>', page)
    for i, tag in enumerate(alternates):
        page = page.replace(tag, f'__ALTERNATE_{i}__')
    for route in ('tools/before-you-build-ai.html', 'about.html', 'writing/start-with-the-decision.html', 'writing/'):
        page = page.replace('https://a-samadi.com/' + route, f'https://a-samadi.com/{lang}/' + route)
    page = page.replace('"item": "https://a-samadi.com/"', f'"item": "https://a-samadi.com/{lang}/"')
    for i, tag in enumerate(alternates):
        page = page.replace(f'__ALTERNATE_{i}__', tag)
    page = re.sub(r'\n(?:\s*\n)?(<script src="/js/site-analytics\.js[^"]*" defer></script>)', r'\n<link rel="stylesheet" href="../../css/rtl.css?v=20261009-lagoon4"><link rel="stylesheet" href="../../css/decision-guide-rtl.css?v=1">\n\1', page, count=1)
    english_label = {'fa': 'مطالعه راهنما به انگلیسی ←', 'ar': 'اقرأ الدليل بالإنجليزية ←'}[lang]
    english_link = f'<p class="byline"><a href="/tools/before-you-build-ai.html" hreflang="en" data-locale-primary="en">{english_label}</a></p>'
    assert page.count('</section>\n<noscript>') == 1, f'{lang}: missing guide intro insertion point'
    page = page.replace('</section>\n<noscript>', '</section>\n' + english_link + '\n<noscript>', 1)
    js = js.replace('decision-brief-ahmadreza-samadi.txt', f'decision-brief-ahmadreza-samadi-{lang}.txt')
    # Bind static startup geometry to the actual localized default runtime output.
    page = subprocess.run(['node', str(ROOT / 'scripts/render_guide_startup.mjs')], input=json.dumps({'html': page, 'script': js}), text=True, capture_output=True, check=True).stdout
    destination = ROOT / lang / 'tools/before-you-build-ai.html'
    # Social metadata copied from the English page is rebuilt in this page's language.
    for key in ('og:site_name', 'og:locale:alternate', 'og:locale', 'og:image:alt', 'twitter:title', 'twitter:description', 'twitter:image:alt'):
        page = re.sub(r'<meta\s+(?:property|name)="' + re.escape(key) + r'"\s+content="[^"]*"\s*/?>\n?', '', page)
    page, _ = enrich(destination, page)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(enrich_follow(page))
    (ROOT / f'js/decision-guide-{lang}.js').write_text(js)
    print(f'Generated {lang}: page, examples, every guidance branch and export text')
