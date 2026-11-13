"""Apply nonvisual page semantics and tie video metadata to the published caption resources."""
from functools import lru_cache
from pathlib import Path
import re
from urllib.parse import urlsplit
from seo_document import Document

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://a-samadi.com/'
MODULES = {'article-author','article-reading-path','follow-subscribe'}
RIGHTS = ('creator', 'creditText', 'copyrightNotice', 'acquireLicensePage')
ARTICLE_MAIN = re.compile(r'(<main\b[^>]*>)(.*?)(</main>)', re.S)
HUB = '<nav class="article-reading-path" aria-labelledby="article-related-title">'
HUB_SECTION = '<aside aria-labelledby="article-related-title">'+HUB

UNCORROBORATED_EXTERNAL_IDS = {
    'https://www.crunchbase.com/organization/appraiva-technologies-inc',
    'https://www.crunchbase.com/organization/royal-abraj-group',
    'https://www.instagram.com/appraiva/',
    'https://www.linkedin.com/company/136184674/',
    'https://www.linkedin.com/company/appraiva/',
    'https://www.linkedin.com/school/shahidbeheshtiuniversityofficial/',
    'https://www.wikidata.org/wiki/Q104659521',
    'https://www.wikidata.org/wiki/Q11660',
    'https://www.wikidata.org/wiki/Q2539',
    'https://www.wikidata.org/wiki/Q4826487',
    'https://www.wikidata.org/wiki/Q684740',
    'https://www.youtube.com/@appraiva',
}

@lru_cache(maxsize=1)
def film_sources():
    sources = {}
    for page in sorted((ROOT/'watch').glob('*.html')):
        doc = Document(page.read_text())
        players = doc.tags('video')
        if len(players) != 1:
            continue
        player = players[0]
        url = next((n.get('src') for n in player.children if getattr(n,'tag','')=='source'), None)
        captions = next((n.get('src') for n in player.children if getattr(n,'tag','')=='track' and n.get('kind')=='captions'),None)
        if url and captions and (ROOT/captions.lstrip('/')).is_file():
            sources[BASE+url.lstrip('/')] = BASE+captions.lstrip('/')
    return sources

def refine_record(node, path):
    """Return True only if this particular record changed."""
    kind = node.get('@type')
    changed = False
    if kind=='ImageObject' and node.get('@id')==BASE+'#portrait':
        for key in RIGHTS:
            if key in node:
                del node[key]
                changed = True
    if kind in ('CollegeOrUniversity', 'DefinedTerm', 'Organization') and 'sameAs' in node:
        original = node['sameAs']
        values = original if isinstance(original, list) else [original]
        supported = [url for url in values if url not in UNCORROBORATED_EXTERNAL_IDS]
        if len(supported) != len(values):
            if supported:
                node['sameAs'] = supported if isinstance(original, list) else supported[0]
            else:
                del node['sameAs']
            changed = True
    if kind=='Organization' and node.get('@id')==BASE+'#appraiva' and 'logo' in node:
        del node['logo']
        changed = True
    if kind=='ListItem' and path in ('ar/work/index.html','fa/work/index.html'):
        old=node.get('url','');prefix=BASE+path[:2]+'/'
        if old.startswith(prefix) and old[len(prefix):] in ('studies/rent-burden/','tools/rental-cash-flow.html','tools/dubai-purchase-cost.html'):
            node['url']=BASE+old[len(prefix):]
            changed=True
    if kind == 'Article' and 'keywords' in node:
        # These optional labels lack visible support on the relevant reviewed edition.
        slug = path.rsplit('/', 1)[-1]
        by_article = {
            'ai-agent-safety-boundaries.html': {'AI agent permissions', 'agent security', 'NVIDIA Sentry',
                                                'صلاحيات وكيل الذكاء الاصطناعي', 'مجوز عامل هوش مصنوعی'},
            'connected-ai-apps.html': {'AI permissions', 'OAuth scope'},
            'jev-ai-decision-model.html': {'AI routing'},
        }
        unsupported = by_article.get(slug, set())
        if slug == 'start-with-the-decision.html' and path.startswith(('ar/', 'fa/')):
            unsupported = {'AI product strategy', 'product decisions', 'AI evaluation', 'decision-first product design'}
        keywords = node['keywords']
        if isinstance(keywords, list) and unsupported.intersection(keywords):
            supported = [item for item in keywords if item not in unsupported]
            if supported:
                node['keywords'] = supported
            else:
                del node['keywords']
            changed = True
    if kind=='VideoObject':
        # All three localized articles embed the identical English on-screen explainer.
        english_explainers = {
            BASE+'assets/writing/geospatial-ai-map-answer-review/explainer.mp4',
            BASE+'assets/writing/virtual-machine-device-sharing-explained/explainer.mp4',
            BASE+'assets/writing/where-wearable-ai-computation-runs/explainer.mp4',
        }
        if node.get('contentUrl') in english_explainers and node.get('inLanguage') != 'en':
            node['inLanguage'] = 'en'
            changed = True
        caption=film_sources().get(node.get('contentUrl',''))
        if caption and node.get('caption')!=caption:
            node['caption']=caption
            changed=True
    return changed

def semantics(text, path):
    """Preserve every text node. Generators call this after other page transforms."""
    # The four visible topic labels belong to the portrait composition and convey information.
    text = text.replace('<ul class="frame-tags" aria-hidden="true">', '<ul class="frame-tags">')
    parts=path.split('/')
    if parts[0] in ('fa','ar'):
        parts=parts[1:]
    if len(parts)==2 and parts[0]=='writing' and parts[1]!='index.html':
        def article(m):
            body=m[2]
            if re.search(r'<article\b',body) or '<h1' not in body:
                return m[0]
            # Retain breadcrumb navigation as a sibling outside the primary article.
            first=re.search(r'<(?:p class="eyebrow"|h1\b)',body)
            end=re.search(r'<!-- (?:article-hub|author-box|follow)[^>]*:start -->|<aside\b|<footer\b',body)
            if not first or not end or first.start()>=end.start():
                return m[0]
            return m[1]+body[:first.start()]+'<article>'+body[first.start():end.start()]+'</article>'+body[end.start():]+m[3]
        text=ARTICLE_MAIN.sub(article,text,count=1)
    if HUB in text and HUB_SECTION not in text:
        text=re.sub(re.escape(HUB)+r'(.*?)</nav>',lambda m:HUB_SECTION+m[1]+'</nav></aside>',text,count=1,flags=re.S)
    if 'tools' in parts and re.search(r'<form\b',text):
        text=re.sub(r'<h1(?![^>]*\bid=)([^>]*)>',r'<h1 id="tool-title"\1>',text,count=1)
        h1=re.search(r'<h1[^>]*\bid="([^"]+)"',text)
        if h1:
            text=re.sub(r'<form(?![^>]*aria-labelledby)(\b[^>]*)>',lambda m:'<form aria-labelledby="'+h1[1]+'"'+m[1]+'>',text,count=1)
        if 'data-status' in text:
            text=text.replace('<p class="status" role="status"', '<p id="calculator-status" class="status" role="status"')
            text=re.sub(r'<output(?![^>]*aria-describedby)(\b[^>]*)>',r'<output aria-describedby="calculator-status"\1>',text)
        text=text.replace('<p id="status" class="status" role="status">','<p id="status" class="status" role="status" aria-live="polite">')
        text=text.replace('<div id="brief-content">','<div id="brief-content" aria-labelledby="brief-heading" aria-describedby="status">')
    if 'studies/' in path:
        text=re.sub(r'(<(?:input|select)\b[^>]*\bid="(?:search|preset|scenario|dataset)")((?:(?!aria-describedby)[^>])*)>',lambda m:m[1]+' aria-describedby="'+('results' if 'id="results"' in text else 'count')+'"'+m[2]+'>' if 'id="results"' in text or 'id="count"' in text else m[0],text)
    return text
