"""Offline integrity checks for crawl policy, page revisions and machine companions."""
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib import robotparser
from xml.etree import ElementTree
from answer_resources import ROOT, PAGES, REVISIONS, PERSON, PORTRAIT, DESCRIPTION, markdown, mirror_path
from seo_document import Document, nodes
from build_llms import build as catalogues

SEARCH_CRAWLERS = ('GPTBot','OAI-SearchBot','ChatGPT-User','ClaudeBot','Claude-SearchBot','Claude-User',
    'PerplexityBot','Perplexity-User','Google-Extended','Googlebot','Bingbot','Applebot','Applebot-Extended',
    'CCBot','Meta-ExternalAgent','Bytespider','Amazonbot','DuckAssistBot','MistralAI-User')
FACTS = {
    'name':r'Ahmadreza Samadi|احمدرضا صمدی|أحمدرضا صمدي',
    'appraiva_role':r'(technical lead|راهبر فنی|مدیر فنی|قائد.{0,4}تقني|القيادة التقنية|قائدا تقنيا|تقنياً).{0,80}Appraiva|Appraiva.{0,100}(technical lead|راهبر فنی|تقنی|تقني)',
    'royal_role':r'(CEO|مدیرعامل|مدیر عامل|رئيس.{0,8}تنفيذي).{0,90}(Royal Abraj|رویال ابراج|رويال أبراج)|(Royal Abraj|رویال ابراج|رويال أبراج).{0,90}(CEO|مدیرعامل|مدیر عامل|رئيس.{0,8}تنفيذي)',
    'dubai':r'Dubai|دبی|دبي',
    'position':r'I build AI, and I run a business|هوش مصنوعی می.سازم و|أبني الذكاء الاصطناعي وأدير|أبني الذكاء الاصطناعي، وأدير'
}

def equal(actual, expected, what):
    if actual != expected:
        raise ValueError(what)

def check_person(person):
    equal(person.get('@id'),PERSON,'wrong Person ID')
    equal(person.get('disambiguatingDescription'),DESCRIPTION,'wrong Person disambiguation')
    image=person.get('image',{})
    for key,value in {'@type':'ImageObject','@id':'https://a-samadi.com/#portrait','url':PORTRAIT,
                      'contentUrl':PORTRAIT,'name':'Ahmadreza Samadi','caption':'Ahmadreza Samadi in a dark suit'}.items():
        equal(image.get(key),value,'wrong Person.image '+key)

def check_robots(text):
    rules=robotparser.RobotFileParser()
    rules.parse(text.splitlines())
    for token in SEARCH_CRAWLERS:
        for path in ('/','/about.html','/fa/about.html','/work/appraiva.html','/llms.txt'):
            if not rules.can_fetch(token,'https://a-samadi.com'+path):
                raise ValueError(f'Unexpected robots restriction for {token} at {path}')
    signals=[s.strip() for s in text.splitlines() if s.lower().startswith('content-signal:')]
    equal(signals,['Content-Signal: search=yes, ai-input=yes'],'review the content-signal change with owner')

def check_facts(text, expected):
    for field in expected:
        if not re.search(FACTS[field],text,re.I):
            raise ValueError('raw HTML lost '+field)

def check_date(lastmod, commit):
    def instant(s):
        return datetime.fromisoformat(s.replace('Z','+00:00')) if len(s)>10 else datetime.fromisoformat(s+'T00:00:00+00:00')
    if instant(lastmod)>instant(commit):
        raise ValueError('sitemap lastmod later than latest page commit')

def raw_text(root):
    def words(el):
        if el.tag in ('script','style','template','noscript') or 'hidden' in el.attrs:
            return
        for child in el.children:
            if isinstance(child,str):
                yield child
            else:
                yield from words(child)
    return ' '.join(' '.join(words(root)).split())

def main():
    check_robots((ROOT/'robots.txt').read_text())
    for path,text in catalogues().items():
        equal((ROOT/path).read_text(),text,'catalogue is not the reproducible published-source output: '+path)
    required = json.loads((ROOT/'scripts/fixtures/raw-biography-coverage.json').read_text())
    expectations={p:flags.split(',') for flags,paths in required.items() for p in paths}
    for p in REVISIONS.keys() | expectations.keys() | set(PAGES):
        source=(ROOT/p).read_text()
        doc=Document(source)
        for b in doc.blocks():
            for n in nodes(json.loads(b)):
                if n.get('@type')=='Person' and (n.get('name')=='Ahmadreza Samadi' or n.get('@id')==PERSON):
                    check_person(n)
        if p in expectations:
            root=next(iter(doc.tags('body')),doc.root)
            try:
                check_facts(raw_text(root),expectations[p])
            except ValueError as exc:
                raise ValueError(f'{p}: {exc}') from exc
        if p in PAGES:
            equal((ROOT/mirror_path(p)).read_text(),markdown(source,p),'Markdown differs from HTML: '+p)
            alternate=[l.get('href') for l in doc.links('alternate') if l.get('type')=='text/markdown']
            equal(alternate,['/'+mirror_path(p)],'missing Markdown alternate: '+p)
    for row in ElementTree.parse(ROOT/'sitemap.xml').getroot():
        url=row.findtext('{*}loc');path=url.removeprefix('https://a-samadi.com/')
        path=path+'index.html' if not path or path.endswith('/') else path
        if path.endswith('.md'):
            raise ValueError('mirror duplicates a canonical sitemap entry')
        last=row.findtext('{*}lastmod')
        if last:
            commit=subprocess.check_output(['git','log','-1','--format=%cI','--',path],cwd=ROOT,text=True).strip()
            if commit:check_date(last,commit)
    print(f'PASS AI-answer resources: {len(PAGES)} mirrors, {len(expectations)} raw-fact baselines, {len(SEARCH_CRAWLERS)} crawler controls')
if __name__=='__main__':
    main()
