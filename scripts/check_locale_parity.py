"""Verify localized homepages retain every English element, destination and asset."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
import re
ROOT=Path(__file__).resolve().parent.parent
class Structure(HTMLParser):
 def __init__(self,url):super().__init__();self.url=url;self.body=False;self.items=[];self.ids=[]
 def handle_starttag(self,t,a):
  if t=='body':self.body=True
  if not self.body:return
  attrs=dict(a)
  if attrs.get('id'):self.ids.append(attrs['id'])
  for k in ['aria-label','alt']:attrs.pop(k,None)
  for k in ['href','src','poster','data-src']:
   if k in attrs and attrs[k] and not attrs[k].startswith('#'):attrs[k]=urljoin(self.url,attrs[k])
  if 'srcset' in attrs:attrs['srcset']=', '.join(urljoin(self.url,x.strip()) for x in attrs['srcset'].split(','))
  self.items.append((t,attrs))
 handle_startendtag=handle_starttag
 def handle_endtag(self,t):
  if self.body:self.items.append(('/'+t,{}))
def parse(path,url):
 p=Structure(url);p.feed(path.read_text());return p
base=parse(ROOT/'index.html','https://a-samadi.com/')
for lang in ['fa','ar']:
 p=parse(ROOT/lang/'index.html',f'https://a-samadi.com/{lang}/')
 normalized=[]
 for tag,attrs in p.items:
  attrs=attrs.copy()
  if attrs.get('href','').startswith(f'https://a-samadi.com/{lang}/about.html'):
   attrs['href']=attrs['href'].replace(f'https://a-samadi.com/{lang}/about.html','https://a-samadi.com/about.html',1)
  normalized.append((tag,attrs))
 assert normalized==base.items, f'{lang}: element or asset mismatch'
 assert p.ids==base.ids and len(p.ids)==len(set(p.ids)), f'{lang}: missing/duplicate section IDs'
 s=(ROOT/lang/'index.html').read_text()
 assert f'<html lang="{lang}" dir="rtl">' in s
 assert f'rel="canonical" href="https://a-samadi.com/{lang}/"' in s
 scripts=re.findall(r'<script>(.*?)</script>',s,re.S)
 english=re.findall(r'<script>(.*?)</script>',(ROOT/'index.html').read_text(),re.S)
 import json
 tr=json.loads((ROOT/'locales'/f'{lang}.json').read_text())
 expected=english[-1].replace("'Resume motion'",json.dumps(tr['Resume motion'],ensure_ascii=False)).replace("'Pause motion'",json.dumps(tr['Pause motion'],ensure_ascii=False))
 assert scripts[-1]==expected, f'{lang}: behavior differs'
 print(f'PASS {lang}: {len(p.items)} matching body elements, all section IDs, assets, links and interaction code')
