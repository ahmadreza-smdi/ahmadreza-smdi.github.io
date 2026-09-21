"""Build full RTL homepages from the English source, preserving its layout and behavior."""
from html.parser import HTMLParser
from pathlib import Path
import html
import json
import re
ROOT=Path(__file__).resolve().parent.parent
SOURCE=(ROOT/'index.html').read_text()
class Translator(HTMLParser):
    def __init__(self, translations):
        super().__init__(convert_charrefs=False)
        self.translations=translations; self.body=False; self.skip=False; self.edits=[]
        self.lines=SOURCE.splitlines(keepends=True)
    def source_offset(self):
        line,col=self.getpos();return sum(map(len,self.lines[:line-1]))+col
    def handle_starttag(self,tag,attrs):
        if tag=='body':self.body=True
        if tag in ('script','style'):self.skip=True
        raw=self.get_starttag_text();new=raw
        for key,value in attrs:
            if value is None:continue
            translated=value
            if self.body and key in ('aria-label','alt') and value:
                translated=self.translations[value]
            if key in ('href','src','poster','data-src') and not re.match(r'^(?:[a-z]+:|/|#)',value):translated='../'+value
            if key in ('srcset','imagesrcset'):
                translated=', '.join('../'+v.strip() for v in value.split(','))
            if translated!=value:
                pattern=r'('+re.escape(key)+r'\s*=\s*")([^"]*)(")'
                new=re.sub(pattern,lambda m:m[1]+html.escape(translated,quote=True)+m[3],new)
        if raw!=new:self.edits.append((self.source_offset(),self.source_offset()+len(raw),new))
    handle_startendtag=handle_starttag
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=False
    def handle_data(self,data):
        # Text with character references is translated as a whole below.
        pass
for lang in ('fa','ar'):
    tr=json.loads((ROOT/'locales'/f'{lang}.json').read_text())
    p=Translator(tr);p.feed(SOURCE);out=SOURCE
    for start,end,value in reversed(p.edits):out=out[:start]+value+out[end:]
    head,body=out.split('<body>',1)
    visible,script=body.split('        <script>',1)
    def translate(m):
        raw=m[1];key=html.unescape(raw).strip()
        if not key:return m[0]
        if key not in tr:raise ValueError(f'Missing {lang} translation: {key}')
        leading=raw[:len(raw)-len(raw.lstrip())];trailing=raw[len(raw.rstrip()):]
        return '>'+leading+html.escape(tr[key],quote=False)+trailing+'<'
    visible=re.sub(r'>([^<>]+)<',translate,'<body>'+visible)
    script=script.replace("'Resume motion'",json.dumps(tr['Resume motion'],ensure_ascii=False)).replace("'Pause motion'",json.dumps(tr['Pause motion'],ensure_ascii=False))
    name=tr['Ahmadreza Samadi'];title=name+' | '+tr['Technology entrepreneur']
    description=tr['I’m Ahmadreza Samadi, a technology entrepreneur based in Dubai. I connect product strategy, engineering, and the practical work of building a business.']
    head=head.replace('<html lang="en">',f'<html lang="{lang}" dir="rtl">')
    head=head.replace('<title>Ahmadreza Samadi | Technology Entrepreneur</title>','<title>'+title+'</title>')
    head=head.replace('content="Ahmadreza Samadi | Technology Entrepreneur"','content="'+title+'"')
    head=re.sub(r'(<meta (?:name="(?:description|twitter:description)"|property="og:description") content=")[^"]*',lambda m:m[1]+description,head)
    head=head.replace('<link rel="canonical" href="https://a-samadi.com/"',f'<link rel="canonical" href="https://a-samadi.com/{lang}/"')
    head=head.replace('property="og:url" content="https://a-samadi.com/"',f'property="og:url" content="https://a-samadi.com/{lang}/"')
    head=head.replace('content="en_US"','content="'+('fa_IR' if lang=='fa' else 'ar_AE')+'"')
    head=head.replace('content="Ahmadreza Samadi, Dubai-based founder and technical executive"','content="'+tr['Portrait of Ahmadreza Samadi']+'"')
    def schema(m):
        d=json.loads(m[1]);profile=next(x for x in d['@graph'] if x['@type']=='ProfilePage')
        profile.update({'@id':f'https://a-samadi.com/{lang}/#profile','url':f'https://a-samadi.com/{lang}/','name':title,'description':description,'inLanguage':lang,'dateModified':'2026-09-21'})
        return '<script type="application/ld+json">'+json.dumps(d,ensure_ascii=False,indent=2)+'</script>'
    head=re.sub(r'<script type="application/ld\+json">(.*?)</script>',schema,head,flags=re.S)
    head=head.replace('</head>','    <link rel="stylesheet" href="../css/rtl.css?v=20260921" />\n</head>')
    (ROOT/lang/'index.html').write_text(head+visible+'        <script>'+script)
    print('Built',lang)
