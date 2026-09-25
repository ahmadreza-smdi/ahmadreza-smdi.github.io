"""Verify localized homepage parity and SEO metadata across published pages."""
from html.parser import HTMLParser
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from xml.etree import ElementTree
import json
import re
ROOT=Path(__file__).resolve().parent.parent
BASE='https://a-samadi.com/'
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
  for local_page in ('about.html','work/appraiva.html','work/royal-abraj.html','writing/'):
   if attrs.get('href','').startswith(f'https://a-samadi.com/{lang}/{local_page}'):
    attrs['href']=attrs['href'].replace(f'https://a-samadi.com/{lang}/{local_page}',f'https://a-samadi.com/{local_page}',1)
  normalized.append((tag,attrs))
 assert normalized==base.items, f'{lang}: element or asset mismatch'
 assert p.ids==base.ids and len(p.ids)==len(set(p.ids)), f'{lang}: missing/duplicate section IDs'
 s=(ROOT/lang/'index.html').read_text()
 assert f'<html lang="{lang}" dir="rtl">' in s
 assert f'rel="canonical" href="https://a-samadi.com/{lang}/"' in s
 scripts=re.findall(r'<script>(.*?)</script>',s,re.S)
 english=re.findall(r'<script>(.*?)</script>',(ROOT/'index.html').read_text(),re.S)
 tr=json.loads((ROOT/'locales'/f'{lang}.json').read_text())
 expected=english[-1].replace("'Resume motion'",json.dumps(tr['Resume motion'],ensure_ascii=False)).replace("'Pause motion'",json.dumps(tr['Pause motion'],ensure_ascii=False))
 assert scripts[-1]==expected, f'{lang}: behavior differs'
 print(f'PASS {lang}: {len(p.items)} matching body elements, all section IDs, assets, links and interaction code')

class HeadSEO(HTMLParser):
 def __init__(self):super().__init__();self.language=None;self.canonicals=[];self.alternates=[];self.robots=[]
 def handle_starttag(self,tag,attributes):
  attrs=dict(attributes)
  if tag=='html':self.language=attrs.get('lang')
  if tag=='link' and attrs.get('rel')=='canonical':self.canonicals.append(attrs.get('href'))
  if tag=='link' and attrs.get('rel')=='alternate' and attrs.get('hreflang'):
   self.alternates.append((attrs['hreflang'],attrs.get('href')))
  if tag=='meta' and attrs.get('name')=='robots':self.robots.append(attrs.get('content',''))

def seo(path):
 metadata=HeadSEO();metadata.feed((ROOT/path).read_text());return metadata

namespace='{http://www.sitemaps.org/schemas/sitemap/0.9}'
sitemap=ElementTree.parse(ROOT/'sitemap.xml').getroot()
listed=[item.text for item in sitemap.findall(f'{namespace}url/{namespace}loc')]
assert len(listed)==len(set(listed)), 'duplicate sitemap URL'
for url in listed:
 assert url.startswith(BASE), f'unexpected sitemap URL: {url}'
 relative=url.removeprefix(BASE)
 source=Path(relative+('index.html' if not relative or relative.endswith('/') else ''))
 assert (ROOT/source).is_file(), f'missing sitemap page: {url}'
 assert seo(source).canonicals==[url], f'non-self-canonical sitemap page: {url}'

for cluster in (
 ('index.html','fa/index.html','ar/index.html'),
 ('about.html','fa/about.html','ar/about.html'),
 ('work/appraiva.html','fa/work/appraiva.html','ar/work/appraiva.html'),
 ('work/royal-abraj.html','fa/work/royal-abraj.html','ar/work/royal-abraj.html'),
 ('writing/ai-cost-per-verified-result.html','fa/writing/ai-cost-per-verified-result.html','ar/writing/ai-cost-per-verified-result.html'),
 ('writing/connected-ai-apps.html','fa/writing/connected-ai-apps.html','ar/writing/connected-ai-apps.html'),
 ('writing/jev-ai-decision-model.html','fa/writing/jev-ai-decision-model.html','ar/writing/jev-ai-decision-model.html'),
 ('writing/index.html','fa/writing/index.html','ar/writing/index.html'),
 ('writing/start-with-the-decision.html','fa/writing/start-with-the-decision.html','ar/writing/start-with-the-decision.html'),
):
 urls=[BASE+(name[:-10] if name.endswith('index.html') else name) for name in cluster]
 expected=dict(zip(('en','fa','ar'),urls));expected['x-default']=urls[0]
 for language,name in zip(('en','fa','ar'),cluster):
  metadata=seo(Path(name))
  assert metadata.language==language, f'{name}: language mismatch'
  assert metadata.canonicals==[expected[language]], f'{name}: canonical mismatch'
  assert len(metadata.alternates)==4 and dict(metadata.alternates)==expected, f'{name}: incomplete or non-reciprocal hreflang'
  assert expected[language] in listed, f'{name}: missing from sitemap'
  assert not any('noindex' in directive.lower() for directive in metadata.robots), f'{name}: noindex directive'
  if name in ('index.html','fa/index.html','ar/index.html') or name.endswith('about.html'):
   source=(ROOT/name).read_text()
   schemas=[json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>',source,re.S)]
   profiles=[item for schema in schemas for item in schema.get('@graph',[schema]) if item.get('@type')=='ProfilePage']
   assert len(profiles)==1, f'{name}: expected one ProfilePage'
   modified=profiles[0].get('dateModified')
   if modified:
    parsed=datetime.fromisoformat(modified)
    assert 'T' in modified and parsed.tzinfo is not None, f'{name}: dateModified needs time and timezone'
print(f'PASS SEO: {len(listed)} self-canonical sitemap URLs and 9 reciprocal language clusters')
