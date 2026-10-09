"""Verify localized homepage parity and SEO metadata across published pages."""
from html import unescape
from html.parser import HTMLParser
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
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
 primary_links=[attrs for tag,attrs in p.items if tag=='a' and attrs.get('data-locale-primary')=='en']
 assert len(primary_links)==1 and primary_links[0].get('href')==BASE and primary_links[0].get('hreflang')=='en', f'{lang}: missing primary English homepage link'
 oxfam_links=[attrs for tag,attrs in p.items if tag=='a' and attrs.get('href','').endswith('/work/oxfam-novib.html')]
 assert len(oxfam_links)==1 and oxfam_links[0]['href']==f'{BASE}{lang}/work/oxfam-novib.html', f'{lang}: Oxfam card must link to the localized case study'
 normalized=[]
 skip_primary=False
 for tag,attrs in p.items:
  if tag=='a' and attrs.get('data-locale-primary')=='en':
   skip_primary=True
   continue
  if skip_primary:
   assert tag=='/a', f'{lang}: unexpected markup inside primary English link'
   skip_primary=False
   continue
  attrs=attrs.copy()
  for local_page in ('tools/before-you-build-ai.html','about.html','work/appraiva.html','work/royal-abraj.html','work/oxfam-novib.html','writing/ai-home-value-estimates.html','writing/'):
   if attrs.get('href','').startswith(f'https://a-samadi.com/{lang}/{local_page}'):
    attrs['href']=attrs['href'].replace(f'https://a-samadi.com/{lang}/{local_page}',f'https://a-samadi.com/{local_page}',1)
  normalized.append((tag,attrs))
 assert not skip_primary, f'{lang}: unclosed primary English link'
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
 def __init__(self):super().__init__();self.language=None;self.canonicals=[];self.alternates=[];self.robots=[];self.open_graph={};self.twitter_cards=[];self.titles=[];self.descriptions=[];self.headings=[];self._title=False;self._heading=False
 def handle_starttag(self,tag,attributes):
  attrs=dict(attributes)
  if tag=='html':self.language=attrs.get('lang')
  if tag=='title':self.titles.append('');self._title=True
  if tag=='h1':self.headings.append('');self._heading=True
  if tag=='link' and attrs.get('rel')=='canonical':self.canonicals.append(attrs.get('href'))
  if tag=='link' and attrs.get('rel')=='alternate' and attrs.get('hreflang'):
   self.alternates.append((attrs['hreflang'],attrs.get('href')))
  if tag=='meta' and attrs.get('name')=='robots':self.robots.append(attrs.get('content',''))
  if tag=='meta' and attrs.get('name')=='description':self.descriptions.append(attrs.get('content',''))
  if tag=='meta' and attrs.get('property','').startswith('og:'):
   self.open_graph.setdefault(attrs['property'],[]).append(attrs.get('content',''))
  if tag=='meta' and attrs.get('name')=='twitter:card':self.twitter_cards.append(attrs.get('content',''))
 def handle_endtag(self,tag):
  if tag=='title':self._title=False
  if tag=='h1':self._heading=False
 def handle_data(self,data):
  if self._title:self.titles[-1]+=data
  if self._heading:self.headings[-1]+=data

def seo(path):
 metadata=HeadSEO();metadata.feed((ROOT/path).read_text());return metadata

class AssetRefs(HTMLParser):
 def __init__(self):super().__init__();self.refs=[]
 def handle_starttag(self,tag,attributes):
  attrs=dict(attributes)
  for key in ('src','poster','data-src'):
   if attrs.get(key):self.refs.append(attrs[key])
  for key in ('srcset','imagesrcset'):
   if attrs.get(key):
    self.refs.extend(candidate.strip().split(' ')[0] for candidate in attrs[key].split(','))
  if tag=='link' and attrs.get('href') and {'stylesheet','icon','preload','manifest','apple-touch-icon'} & set((attrs.get('rel') or '').split()):
   self.refs.append(attrs['href'])
  if tag=='meta' and (attrs.get('property')=='og:image' or attrs.get('name')=='twitter:image'):
   self.refs.append(attrs.get('content',''))

def check_local_asset(source,ref):
 if not ref or ref.startswith(('data:','#','blob:')):return
 parsed=urlparse(urljoin(urljoin(BASE,str(source)),ref))
 if parsed.netloc not in ('a-samadi.com','www.a-samadi.com'):return
 target=ROOT/unquote(parsed.path).lstrip('/')
 assert target.is_file(), f'{source}: missing local asset {ref}'

namespace='{http://www.sitemaps.org/schemas/sitemap/0.9}'
sitemap=ElementTree.parse(ROOT/'sitemap.xml').getroot()
listed=[item.text for item in sitemap.findall(f'{namespace}url/{namespace}loc')]
assert len(listed)==len(set(listed)), 'duplicate sitemap URL'
seen_titles={};seen_descriptions={}
for url in listed:
 assert url.startswith(BASE), f'unexpected sitemap URL: {url}'
 relative=url.removeprefix(BASE)
 source=Path(relative+('index.html' if not relative or relative.endswith('/') else ''))
 assert (ROOT/source).is_file(), f'missing sitemap page: {url}'
 metadata=seo(source)
 assert len(metadata.titles)==1 and metadata.titles[0].strip(), f'{source}: missing or duplicate title'
 assert len(metadata.descriptions)==1 and metadata.descriptions[0].strip(), f'{source}: missing or duplicate meta description'
 assert len(metadata.headings)==1 and metadata.headings[0].strip(), f'{source}: missing or duplicate h1'
 for value,seen,label in ((metadata.titles[0].strip(),seen_titles,'title'),(metadata.descriptions[0].strip(),seen_descriptions,'description')):
  assert value not in seen, f'{source}: duplicate {label} also used by {seen.get(value)}'
  seen[value]=source
 assert metadata.canonicals==[url], f'non-self-canonical sitemap page: {url}'
 assert metadata.open_graph.get('og:url')==[url], f'{source}: Open Graph URL differs from canonical'
 for property in ('og:title','og:type','og:image'):
  values=metadata.open_graph.get(property,[])
  assert len(values)==1 and values[0], f'{source}: missing or duplicate {property}'
 assert len(metadata.twitter_cards)==1 and metadata.twitter_cards[0], f'{source}: missing or duplicate Twitter card'
 assets=AssetRefs();assets.feed((ROOT/source).read_text())
 for ref in assets.refs:check_local_asset(source,ref)

video_ns='{http://www.google.com/schemas/sitemap-video/1.1}'
watch_pages={BASE+path.relative_to(ROOT).as_posix() for path in (ROOT/'watch').glob('*.html')}
assert watch_pages <= set(listed), 'watch page missing from sitemap'
for entry in sitemap.findall(f'{namespace}url'):
 url=entry.find(f'{namespace}loc').text
 videos=entry.findall(f'{video_ns}video')
 if url not in watch_pages:
  assert not videos, f'{url}: video entry belongs on a watch page'
  continue
 assert len(videos)==1, f'{url}: expected one sitemap video'
 source=ROOT/url.removeprefix(BASE)
 html=(source).read_text()
 schemas=[json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>',html,re.S)]
 films=[schema for schema in schemas if schema.get('@type')=='VideoObject']
 assert len(films)==1, f'{source}: expected one VideoObject'
 film=films[0]
 fields={'thumbnail_loc':'thumbnailUrl','title':'name','content_loc':'contentUrl'}
 for tag,property in fields.items():
  value=videos[0].findtext(f'{video_ns}{tag}')
  assert value==film[property], f'{source}: video sitemap {tag} differs from VideoObject'
  if tag!='title':check_local_asset(source,value)
 assert film['name']==seo(source).headings[0].strip(), f'{source}: video name differs from visible heading'
 description=videos[0].findtext(f'{video_ns}description')
 assert description and description in html, f'{source}: video description is not visible'

for css in ROOT.rglob('*.css'):
 source=css.relative_to(ROOT)
 for ref in re.findall(r'url\(\s*[\'\"]?([^\)\'\"]+)',css.read_text()):
  check_local_asset(source,ref)

clusters = (
 ('writing/how-contactless-cards-work.html','fa/writing/how-contactless-cards-work.html','ar/writing/how-contactless-cards-work.html'),
 ('writing/how-noise-cancellation-works.html','fa/writing/how-noise-cancellation-works.html','ar/writing/how-noise-cancellation-works.html'),
 ('writing/why-usb-c-cables-differ.html','fa/writing/why-usb-c-cables-differ.html','ar/writing/why-usb-c-cables-differ.html'),
 ('writing/how-photo-text-recognition-works.html','fa/writing/how-photo-text-recognition-works.html','ar/writing/how-photo-text-recognition-works.html'),
 ('writing/iphone-duo-price-per-day.html','fa/writing/iphone-duo-price-per-day.html','ar/writing/iphone-duo-price-per-day.html'),
 ('writing/why-full-storage-slows-computer.html','fa/writing/why-full-storage-slows-computer.html','ar/writing/why-full-storage-slows-computer.html'),
 ('tools/before-you-build-ai.html','fa/tools/before-you-build-ai.html','ar/tools/before-you-build-ai.html'),
 ('index.html','fa/index.html','ar/index.html'),
 ('about.html','fa/about.html','ar/about.html'),
 ('work/appraiva.html','fa/work/appraiva.html','ar/work/appraiva.html'),
 ('work/royal-abraj.html','fa/work/royal-abraj.html','ar/work/royal-abraj.html'),
 ('work/oxfam-novib.html','fa/work/oxfam-novib.html','ar/work/oxfam-novib.html'),
 ('writing/ai-cost-per-verified-result.html','fa/writing/ai-cost-per-verified-result.html','ar/writing/ai-cost-per-verified-result.html'),
 ('writing/connected-ai-apps.html','fa/writing/connected-ai-apps.html','ar/writing/connected-ai-apps.html'),
 ('writing/jev-ai-decision-model.html','fa/writing/jev-ai-decision-model.html','ar/writing/jev-ai-decision-model.html'),
 ('writing/index.html','fa/writing/index.html','ar/writing/index.html'),
 ('writing/start-with-the-decision.html','fa/writing/start-with-the-decision.html','ar/writing/start-with-the-decision.html'),
 ('writing/passkeys-face-id.html','fa/writing/passkeys-face-id.html','ar/writing/passkeys-face-id.html'),
 ('writing/how-zip-files-work.html','fa/writing/how-zip-files-work.html','ar/writing/how-zip-files-work.html'),
 ('writing/ai-agent-safety-boundaries.html','fa/writing/ai-agent-safety-boundaries.html','ar/writing/ai-agent-safety-boundaries.html'),
 ('writing/ai-human-review-real-estate.html','fa/writing/ai-human-review-real-estate.html','ar/writing/ai-human-review-real-estate.html'),
 ('writing/verify-ai-image-claims.html','fa/writing/verify-ai-image-claims.html','ar/writing/verify-ai-image-claims.html'),
 ('writing/foldable-two-batteries.html','fa/writing/foldable-two-batteries.html','ar/writing/foldable-two-batteries.html'),
 ('writing/ai-home-value-estimates.html','fa/writing/ai-home-value-estimates.html','ar/writing/ai-home-value-estimates.html'),
 ('writing/humanoid-robots-at-home.html','fa/writing/humanoid-robots-at-home.html','ar/writing/humanoid-robots-at-home.html'),
 ('writing/how-satellite-messaging-works.html','fa/writing/how-satellite-messaging-works.html','ar/writing/how-satellite-messaging-works.html'),
 ('writing/incognito-private-browsing.html','fa/writing/incognito-private-browsing.html','ar/writing/incognito-private-browsing.html'),
 ('writing/why-ai-sounds-confident.html','fa/writing/why-ai-sounds-confident.html','ar/writing/why-ai-sounds-confident.html'),
 ('writing/why-phone-stops-charging-at-80.html','fa/writing/why-phone-stops-charging-at-80.html','ar/writing/why-phone-stops-charging-at-80.html'),
 ('writing/ai-rental-yield-cash-flow.html','fa/writing/ai-rental-yield-cash-flow.html','ar/writing/ai-rental-yield-cash-flow.html'),
 ('writing/profitable-but-out-of-cash.html','fa/writing/profitable-but-out-of-cash.html','ar/writing/profitable-but-out-of-cash.html'),
 ('writing/what-accept-cookies-means.html','fa/writing/what-accept-cookies-means.html','ar/writing/what-accept-cookies-means.html'),
)
for cluster in clusters:
 urls=[BASE+(name[:-10] if name.endswith('index.html') else name) for name in cluster]
 expected=dict(zip(('en','fa','ar'),urls));expected['x-default']=urls[0]
 for language,name in zip(('en','fa','ar'),cluster):
  metadata=seo(Path(name))
  assert metadata.language==language, f'{name}: language mismatch'
  assert metadata.canonicals==[expected[language]], f'{name}: canonical mismatch'
  assert len(metadata.alternates)==4 and dict(metadata.alternates)==expected, f'{name}: incomplete or non-reciprocal hreflang'
  assert expected[language] in listed, f'{name}: missing from sitemap'
  assert not any('noindex' in directive.lower() for directive in metadata.robots), f'{name}: noindex directive'
  if language!='en' and name.startswith(f'{language}/writing/'):
   body=parse(ROOT/name,expected[language])
   assert any(tag=='a' and attrs.get('href')==expected['en'] and attrs.get('hreflang')=='en' for tag,attrs in body.items), f'{name}: missing visible English writing route'
  if language!='en' and (name.startswith(f'{language}/work/') or name.startswith(f'{language}/tools/')):
   body=parse(ROOT/name,expected[language])
   assert sum(tag=='a' and attrs.get('href')==expected['en'] and attrs.get('hreflang')=='en' and attrs.get('data-locale-primary')=='en' for tag,attrs in body.items)==1, f'{name}: missing primary English work or guide route'
  if name in ('index.html','fa/index.html','ar/index.html') or name.endswith('about.html'):
   source=(ROOT/name).read_text()
   schemas=[json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>',source,re.S)]
   graph=[item for schema in schemas for item in schema.get('@graph',[schema])]
   profiles=[item for item in graph if item.get('@type')=='ProfilePage']
   assert len(profiles)==1, f'{name}: expected one ProfilePage'
   profile=profiles[0]
   assert profile.get('url')==expected[language], f'{name}: ProfilePage URL differs from canonical'
   entity=profile.get('mainEntity',{})
   person=entity if entity.get('@type')=='Person' else next((item for item in graph if item.get('@type')=='Person' and item.get('@id')==entity.get('@id')),None)
   assert person and person.get('@id')==BASE+'#person' and person.get('name')=='Ahmadreza Samadi', f'{name}: inconsistent person identity'
   assert {'احمدرضا صمدی','أحمدرضا صمدي','Ahmad Samadi'} <= set(person.get('alternateName',[])), f'{name}: missing established name variation'
   assert {'https://www.instagram.com/ahmadreza_smdi/','https://www.linkedin.com/in/ahmadreza-samadi/'} <= set(person.get('sameAs',[])), f'{name}: missing official social identity link'
   modified=profile.get('dateModified')
   if modified:
    parsed=datetime.fromisoformat(modified)
    assert 'T' in modified and parsed.tzinfo is not None, f'{name}: dateModified needs time and timezone'
   if name in ('index.html','fa/index.html','ar/index.html'):
    updated=re.search(r'<meta property="og:updated_time" content="([^"]+)"',source)
    assert updated and modified==updated[1], f'{name}: ProfilePage and Open Graph update times differ'
    if name in ('fa/index.html','ar/index.html'):
     locale=name[:2]
     expected_modified=json.loads((ROOT/'locales'/f'{locale}.json').read_text())['Homepage modified']
     assert modified==expected_modified, f'{name}: localized homepage modification time differs from source'
for name in ('writing/index.html','fa/writing/index.html','ar/writing/index.html'):
 source=(ROOT/name).read_text()
 schemas=[json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>',source,re.S)]
 collections=[item for schema in schemas for item in schema.get('@graph',[schema]) if item.get('@type')=='CollectionPage']
 assert len(collections)==1, f'{name}: expected one CollectionPage'
 collection=collections[0]
 item_list=collection.get('mainEntity',{})
 assert item_list.get('@type')=='ItemList', f'{name}: missing ItemList'
 cards=[(urljoin(BASE,href),unescape(title.strip())) for href,title in re.findall(r'<article>\s*<h2><a href="([^"]+)"[^>]*>(.*?)</a></h2>',source,re.S)]
 assert len(cards)==source.count('<article>'), f'{name}: an article card has no matching heading link'
 assert cards and len(cards)==len(set(url for url,_ in cards)), f'{name}: missing or duplicate visible cards'
 assert all(url in listed for url,_ in cards), f'{name}: visible card URL missing from sitemap'
 items=item_list.get('itemListElement',[])
 assert item_list.get('numberOfItems')==len(cards)==len(items), f'{name}: ItemList count differs from visible cards'
 for position,((url,title),item) in enumerate(zip(cards,items),1):
  assert (item.get('@type'),item.get('position'),item.get('url'),item.get('name'))==('ListItem',position,url,title), f'{name}: ItemList differs from visible card {position}'
 print(f'PASS {name}: {len(cards)} visible writing cards match ItemList')
for lang in ('fa','ar'):
 for source,local_target,old_english_target in (
  (f'{lang}/writing/index.html',f'{lang}/work/oxfam-novib.html','work/oxfam-novib.html'),
  (f'{lang}/writing/ai-cost-per-verified-result.html',f'{lang}/tools/before-you-build-ai.html','tools/before-you-build-ai.html'),
 ):
  url=BASE+(source[:-10] if source.endswith('index.html') else source)
  links=[attrs.get('href') for tag,attrs in parse(ROOT/source,url).items if tag=='a']
  assert links.count(BASE+local_target)==1, f'{source}: expected one link to translated {local_target}'
  assert BASE+old_english_target not in links, f'{source}: stale English-only link to {old_english_target}'
print('PASS localized links: Oxfam hubs and AI-cost guides use translated destinations')
article_pages=sorted(path for path in ROOT.glob('**/writing/*.html') if path.name!='index.html')
for path in article_pages:
 source=path.read_text()
 schemas=[json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>',source,re.S)]
 articles=[item for schema in schemas for item in schema.get('@graph',[schema]) if item.get('@type')=='Article']
 assert len(articles)==1 and articles[0].get('description','').strip(), f'{path.relative_to(ROOT)}: missing Article description'
 relative=path.relative_to(ROOT)
 language=relative.parts[0] if relative.parts[0] in ('fa','ar') else 'en'
 biography=BASE+(f'{language}/' if language!='en' else '')+'about.html'
 author=articles[0].get('author',{})
 assert author.get('@type')=='Person' and author.get('@id')==BASE+'#person', f'{relative}: inconsistent author entity'
 expected_names={'en':{'Ahmadreza Samadi'},'fa':{'Ahmadreza Samadi','احمدرضا صمدی'},'ar':{'Ahmadreza Samadi','أحمدرضا صمدي'}}
 assert author.get('name') in expected_names[language] and author.get('url')==biography, f'{relative}: inconsistent author biography'
 article_url=articles[0].get('url')
 assert article_url in listed, f'{relative}: article URL missing from sitemap'
 if language in ('fa','ar'):
  english_url=BASE+'writing/'+path.name
  expected_translation={'@id': english_url+'#article'}
  assert articles[0].get('translationOfWork')==expected_translation, f'{relative}: missing or incorrect English original in Article schema'
 body=parse(path,article_url)
 assert any(tag=='a' and attrs.get('href')==biography and 'author' in attrs.get('rel','').split() for tag,attrs in body.items), f'{relative}: missing visible author link'
print(f'PASS article metadata: {len(article_pages)} articles have descriptions and one shared, visibly linked author')
print(f'PASS SEO: {len(listed)} self-canonical sitemap URLs and {len(clusters)} reciprocal language clusters')
