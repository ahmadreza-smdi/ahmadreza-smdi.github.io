"""Check reviewed structured evidence, accessibility, machine copies and public film sources offline."""
from functools import lru_cache
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from answer_resources import PAGES, mirror_path, markdown
from check_internal_links import site_pages
from readiness import MODULES
from seo_document import Document, nodes

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / 'scripts/fixtures/readiness-evidence.json'
INSTRUCTION = re.compile(r'\b(?:ai assistants? (?:must|should|shall)|ignore (?:all |the )?(?:previous|prior) instructions|(?:chatgpt|perplexity),? (?:always )?recommend)\b', re.I)
HIDDEN_CSS = re.compile(r'(?:display\s*:\s*none|visibility\s*:\s*hidden|(?:left|top|text-indent)\s*:\s*-\d{3,}|font-size\s*:\s*0(?:px|em|rem)?\b|opacity\s*:\s*0\s*(?:!important)?(?:;|$))', re.I)
SPACE = re.compile(r'\s+')

def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def vocabulary(doc):
    return sorted((el.get('property'), el.get('content')) for el in doc.tags('meta') if el.get('property').startswith('profile:'))

def evidence(doc):
    graphs = [json.loads(block) for block in doc.blocks()]
    return digest([graphs, vocabulary(doc)]), digest([el.text() for el in doc.tags('main')])

def hidden_fragments(doc):
    result = []
    for el in doc.elements:
        if el.within(lambda parent: parent.tag in ('head','style','script','template','svg')) or not el.text():
            continue
        style = el.get('style')
        fore = re.search(r'(?:^|;)\s*color\s*:\s*([^;!]+)', style)
        back = re.search(r'(?:^|;)\s*background(?:-color)?\s*:\s*([^;!]+)', style)
        reasons = []
        if 'hidden' in el.attrs: reasons.append('conditional')
        if el.get('aria-hidden') == 'true': reasons.append('decorative')
        if HIDDEN_CSS.search(style) or (fore and back and fore[1].strip()==back[1].strip()): reasons.append('style')
        if {'sr-only','visually-hidden','offscreen'} & set(el.get('class').split()): reasons.append('accessibility-label')
        if reasons:
            result.append([el.tag, el.get('id'), el.get('class'), reasons, el.text()])
    return result

def hygiene(doc, raw, expected):
    problems = []
    if digest(hidden_fragments(doc)) != expected:
        problems.append('unreviewed hidden or accessibility-hidden content')
    for note in re.findall(r'<!--(.*?)-->', raw, re.S):
        if INSTRUCTION.search(note): problems.append('assistant instruction in a comment')
    for elem in doc.elements:
        if INSTRUCTION.search(elem.get('alt')) or INSTRUCTION.search(elem.get('title')):
            problems.append('assistant instruction in a media label')
    if any(INSTRUCTION.search(str(x)) for x in hidden_fragments(doc)) or any(INSTRUCTION.search(b) for b in doc.blocks()):
        problems.append('assistant instruction in a hidden or machine-readable field')
    return problems

def landmarks(doc,path):
    problems = []
    if len(doc.tags('main')) != 1: problems.append('expected exactly one main')
    for el in doc.elements:
        cl = set(el.get('class').split())
        if cl & {'article-author','article-reading-path'} and not el.within(lambda n:n.tag=='aside'):
            problems.append('author or related module outside aside')
        if 'article-reading-path' in cl and el.tag!='nav': problems.append('reading path without nav')
    if '/writing/' in '/'+path and not path.endswith('/index.html') and doc.tags('h1') and not doc.tags('article'):
        problems.append('article body lacks an article landmark')
    return problems

def widgets(doc,path):
    if all(folder not in '/'+path for folder in ('/tools/','/studies/')): return []
    problems = []
    labels={el.get('for') for el in doc.tags('label') if el.text()}
    ids={e.get('id'):e for e in doc.elements if e.get('id')}
    controls=[e for e in doc.elements if e.tag in ('select','textarea','input') and e.get('type')!='hidden']
    for el in controls:
        referenced=el.get('aria-labelledby').split()
        if not (el.get('aria-label') or el.get('id') in labels or el.within(lambda n:n.tag=='label' and n.text()) or
                referenced and all(key in ids and ids[key].text() for key in referenced)):
            problems.append('unnamed control '+(el.get('id') or el.tag))
    if controls and not any(e.get('aria-live') in ('polite','assertive') or e.get('role')=='status' for e in doc.elements):
        problems.append('interactive page lacks result announcements')
    for el in doc.tags('output'):
        if not el.get('aria-describedby') or not all(key in ids for key in el.get('aria-describedby').split()):
            problems.append('output lacks a valid description')
    return problems

def boilerplate(doc, machine):
    flat=SPACE.sub(' ',re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',machine)).casefold()
    for el in doc.elements:
        if MODULES.intersection(el.get('class').split()):
            for child in el.children:
                if isinstance(child,str): continue
                phrase=child.text().casefold()
                if len(phrase.split())>=7 and phrase in flat: return ['repeated author, follow or related module in machine text']
    return []

@lru_cache(maxsize=2)
def film_texts(root):
    films={}
    for path in sorted((root/'watch').glob('*.html')):
        doc=Document(path.read_text())
        source=next((e.get('src') for e in doc.tags('source') if e.within(lambda n:n.tag=='video')),None)
        if not source: continue
        options=set()
        for details in doc.tags('details'):
            if 'transcript' in details.get('class').split():
                options.add(' '.join(p.text() for p in doc.tags('p') if p.within(lambda n:n is details)))
        tracks={e.get('src') for e in doc.tags('track') if e.get('kind')=='captions'}
        for filename in tracks:
            cues=(root/filename.lstrip('/')).read_text().splitlines()
            options.add(' '.join(x.strip() for x in cues if x.strip() and x.strip()!='WEBVTT' and '-->' not in x and not x.strip().isdigit()))
        films[urlsplit(source).path] = (options,tracks)
    return films

def media(doc,films):
    problems=[]
    for block in doc.blocks():
        for node in nodes(json.loads(block)):
            if node.get('@type')!='VideoObject': continue
            options,tracks=films.get(urlsplit(node.get('contentUrl','')).path,(set(),set()))
            if node.get('transcript') and node['transcript'] not in options: problems.append('transcript differs from published words')
            if tracks and urlsplit(node.get('caption','')).path not in tracks: problems.append('missing or incorrect caption source')
            if node.get('caption') and not tracks: problems.append('caption has no published track')
    return problems

def parity(doc,expected):
    return [] if list(evidence(doc))==expected else ['structured claim or its visible evidence changed and needs review']

def main():
    pins=json.loads(PINS.read_text())
    bad=[];films=film_texts(ROOT)
    for path in site_pages(ROOT):
        rel=path.relative_to(ROOT).as_posix();raw=path.read_text();doc=Document(raw);pin=pins['pages'].get(rel)
        if pin is None:bad.append((rel,'missing evidence review'));continue
        for error in parity(doc,pin[:2])+hygiene(doc,raw,pin[2])+landmarks(doc,rel)+widgets(doc,rel)+media(doc,films):
            bad.append((rel,error))
        if rel in PAGES:
            output=(ROOT/mirror_path(rel)).read_text()
            if output!=markdown(raw,rel):bad.append((rel,'mirror differs from reviewed visible blocks'))
            for error in boilerplate(doc,output): bad.append((rel,error))
        # The catalogue deliberately includes the press kit's own biography choices.
        # Check each source excerpt before it enters the catalogue. The byte-exact catalogue
        # builder check catches later reintroductions or duplicated whole excerpts.
        if rel in PAGES and not rel.startswith(('fa/','ar/')):
            excerpt=markdown(raw,rel)
            if rel!='press.html':
                for error in boilerplate(doc,excerpt):bad.append((rel,error))
    for name,hashval in pins['styles'].items():
        if sha256((ROOT/name).read_bytes()).hexdigest()!=hashval:bad.append((name,'recheck CSS selectors for hidden content'))
    for name in ['llms.txt','llms-full.txt',*(mirror_path(p) for p in PAGES)]:
        if INSTRUCTION.search((ROOT/name).read_text()):bad.append((name,'machine copy addresses assistants'))
    for item in bad: print('FAIL',*item)
    if bad: return 1
    print('PASS: reviewed structured and visible evidence, hidden text, landmarks, widgets, boilerplate and film sources')
    return 0

if __name__=='__main__': raise SystemExit(main())
