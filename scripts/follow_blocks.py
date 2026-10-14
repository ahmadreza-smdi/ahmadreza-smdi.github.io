#!/usr/bin/env python3
"""Prepare locale-aware conversion navigation without touching the checkout."""
import argparse, hashlib, html, json, re, subprocess
from pathlib import Path
from html.parser import HTMLParser

START = '<!-- follow-subscribe:start -->'
END = '<!-- follow-subscribe:end -->'
LABELS = {'en': ('Follow / Subscribe', 'Follow Ahmadreza Samadi', 'Get the weekly brief'),
          'fa': ('دنبال کردن / اشتراک', 'دنبال کردن احمدرضا صمدی', 'دریافت خلاصهٔ هفتگی'),
          'ar': ('المتابعة / الاشتراك', 'متابعة أحمدرضا صمدي', 'احصل على الموجز الأسبوعي')}
class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.lang=None; self.canonical=None; self.scripts=[]; self.on=False; self.data=''
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='html': self.lang=a.get('lang')
        if tag=='link' and a.get('rel')=='canonical': self.canonical=a.get('href')
        if tag=='script' and a.get('type')=='application/ld+json': self.on=True; self.data=''
    def handle_data(self, data):
        if self.on: self.data+=data
    def handle_endtag(self, tag):
        if tag=='script' and self.on:
            self.scripts.append(json.loads(self.data)); self.on=False

def render(language, config):
    title, label, brief = LABELS[language]
    links=[(name, config[name]) for name in ('YouTube','Instagram','LinkedIn')]
    if config.get('newsletter'):
        links.insert(0, (brief, config['newsletter']))
    anchors=' · '.join(f'<a href="{html.escape(url, quote=True)}"><bdi>{html.escape(name)}</bdi></a>' for name,url in links)
    return f'{START}\n<aside class="details follow-subscribe" aria-labelledby="follow-subscribe-title">\n<h2 id="follow-subscribe-title">{title}</h2>\n<nav aria-label="{label}">{anchors}</nav>\n</aside>\n{END}\n'

def transform(source, config):
    page=Page(); page.feed(source)
    if page.lang not in LABELS: raise ValueError('Unsupported page language')
    if source.count(START)!=source.count(END) or source.count(START)>1: raise ValueError('Malformed markers')
    block=render(page.lang, config)
    if START in source:
        return re.sub(re.escape(START)+r'.*?'+re.escape(END)+r'\n?', lambda m:block, source, flags=re.S)
    if 'id="follow-subscribe-title"' in source: raise ValueError('Existing heading ID collision')
    if source.count('</article>')==1: return source.replace('</article>',block+'</article>',1)
    footer=re.search(r'<footer\b[^>]*class="[^"]*editorial-footer[^\"]*"',source)
    close=source.find('</main>')
    if close<0: raise ValueError('No main element')
    index=footer.start() if footer and footer.start()<close else close
    return source[:index]+block+source[index:]

def enrich_follow(source):
    config=json.loads((Path(__file__).resolve().parent.parent/'locales/follow-links.json').read_text())
    return transform(source,config)

def main():
    import argparse
    parser=argparse.ArgumentParser(description='Maintain locale-aware follow navigation on canonical growth pages.')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    changes=[];count=0
    for path in sorted(root.rglob('*.html')):
        name=path.relative_to(root).as_posix()
        if any(part.startswith('.') for part in path.relative_to(root).parts):continue
        source=path.read_text();page=Page();page.feed(source)
        if not page.canonical or page.lang not in LABELS:continue
        nodes=[]
        for doc in page.scripts:nodes.extend(doc.get('@graph',[doc]))
        article=any(n.get('@type')=='Article' for n in nodes)
        route=bool(re.fullmatch(r'(fa/|ar/)?(topics|tools)/[^/]+\.html',name))
        brief=name in ('index.html','fa/index.html','ar/index.html','about.html','fa/about.html','ar/about.html')
        study=bool(re.fullmatch(r'studies/[^/]+/index\.html',name))
        if not (article or route or brief or study):continue
        result=enrich_follow(source);count+=1
        if result!=source:changes.append((path,source,result))
    if args.check:
        for path,_,_ in changes:print('STALE',path.relative_to(root))
        if changes:raise SystemExit(1)
    else:
        for path,source,result in changes:
            if path.read_text()!=source:raise RuntimeError('Concurrent edit: '+str(path))
            path.write_text(result)
    print(f'PASS follow navigation: {count} eligible pages, {len(changes)} changes')

if __name__=='__main__':main()
