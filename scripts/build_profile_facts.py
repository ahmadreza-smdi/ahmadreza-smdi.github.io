"""Keep dated About facts and Person role dates aligned in all three locales."""
from pathlib import Path
import html,json,re,sys
ROOT=Path(__file__).resolve().parent.parent
DATA=json.loads((ROOT/'locales/profile-facts.json').read_text())
SUBJECTS=[('Artificial intelligence','Q11660'),('Machine learning','Q2539'),('Real estate','Q684740'),('Automated valuation','Q4826487'),('Data engineering','Q104659521')]
FACTS='''## Facts — as of October 2026

- Based in Dubai, United Arab Emirates; also known as Ahmad Samadi.
- Co-Founder & Technical Lead of Appraiva since October 2023. Appraiva is based in Cleveland, Ohio, United States; he works remotely from Dubai. It builds AI tools for investors and developers to find distressed and off-market properties through imagery analysis and enriched property data.
- Co-Founder & CEO of Royal Abraj Group since 2022. The Dubai group covers property brokerage and documents-clearing services; he leads digital strategy and technology. The start month is not stated.
- Background: enterprise data engineering and machine learning; Azure data infrastructure for CRM migration and analytics at Oxfam Novib; predictive customer segmentation at MCI.
- Education: Master of Science in Computer Software Engineering, specialization in Data, Shahid Beheshti University, 2019–2021.
- Spoken languages are not stated in the approved biography/CV. Translated pages do not establish language proficiency.
- Contact: ahmadreza.smdi@gmail.com.
- Other people share the name Ahmad Samadi; this is the official site of the Dubai-based technology entrepreneur.
'''
def paragraph(s):
    return html.escape(s).replace('ahmadreza.smdi@gmail.com','<a href="mailto:ahmadreza.smdi@gmail.com">ahmadreza.smdi@gmail.com</a>')
def section(d):
    facts=''.join('<div><dt>'+paragraph(k)+'</dt><dd>'+paragraph(v)+'</dd></div>' for k,v in d['facts'])
    qa=''.join('<h3>'+paragraph(q)+'</h3><p>'+paragraph(a)+'</p>' for q,a in d['qa'])
    return '<section class="profile-resources quick-facts" id="at-a-glance" aria-labelledby="at-a-glance-title"><h2 id="at-a-glance-title">'+paragraph(d['heading'])+'</h2><p>'+paragraph(d['intro'])+'</p><dl class="quick-facts-list">'+facts+'</dl><p>'+paragraph(d['disambiguation'])+'</p></section>\n<section class="profile-resources" id="profile-questions" aria-labelledby="profile-questions-title"><h2 id="profile-questions-title">'+paragraph(d['qa_title'])+'</h2>'+qa+'</section>'
def person_schema(m):
    d=json.loads(m[1]);nodes=[]
    def collect(value):
        if isinstance(value,dict):
            nodes.append(value)
            for child in value.values():collect(child)
        elif isinstance(value,list):
            for child in value:collect(child)
    collect(d)
    for n in nodes:
        if n.get('@type')!='Person' or n.get('@id')!='https://a-samadi.com/#person':continue
        n['jobTitle']=['Co-Founder & Technical Lead, Appraiva','Co-Founder & CEO, Royal Abraj Group']
        n['knowsAbout']=[{'@type':'DefinedTerm','name':name,'sameAs':'https://www.wikidata.org/wiki/'+qid} for name,qid in SUBJECTS]
        # Schema.org's Role pattern attaches dates to the association, not to an Occupation.
        n['worksFor']=[{'@type':'OrganizationRole','roleName':title,'startDate':start,'worksFor':{'@id':'https://a-samadi.com/#'+org}} for title,start,org in [('Co-Founder & Technical Lead','2023-10','appraiva'),('Co-Founder & CEO','2022','royal-abraj')]]
        n['hasOccupation']=[{'@type':'Occupation','name':'Co-Founder & Technical Lead at Appraiva','description':'Held since October 2023; remote from Dubai.','responsibilities':'AI tools for property discovery using imagery analysis and enriched property data.'},{'@type':'Occupation','name':'Co-Founder & CEO at Royal Abraj Group','description':'Held since 2022.','responsibilities':'Digital strategy and technology.'}]
    return '<script type="application/ld+json">\n'+json.dumps(d,ensure_ascii=False,indent=2)+'\n</script>'
def about_parity(text,lang):
    """Reuse supported English facts; preserve each locale's copy and canonical identity."""
    source=(ROOT/'about.html').read_text()
    graphs=[json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>',source,re.S)]
    entities=[n for g in graphs for n in g.get('@graph',[g])]
    person=next(n for n in entities if n.get('@type')=='Person')
    def align(m):
        data=json.loads(m[1]);graph=data.get('@graph',[data])
        profile=next((n for n in graph if n.get('@type')=='ProfilePage'),None)
        if profile is None:return m[0]
        target=profile.get('mainEntity',{})
        if target.get('@type')=='Person':
            for key in ('givenName','familyName','jobTitle','alumniOf','homeLocation','memberOf'):
                target[key]=person[key]
            target['mainEntityOfPage']={'@id':profile['@id']}
        profile['isPartOf']={'@id':'https://a-samadi.com/#website'}
        ids={n.get('@id') for n in graph}
        for entity in entities:
            if entity.get('@type') not in ('WebSite','Organization') or entity.get('@id') in ids:continue
            # Corroborating organizations, without adding company contact or administration fields.
            keys=('@type','@id','name','url','description') if entity['@type']=='Organization' else tuple(entity)
            graph.append({key:entity[key] for key in keys if key in entity})
        for n in graph:n.pop('@context',None)
        return '<script type="application/ld+json">\n'+json.dumps({'@context':'https://schema.org','@graph':graph},ensure_ascii=False,indent=2)+'\n</script>'
    return re.sub(r'<script type="application/ld\+json">(.*?)</script>',align,text,flags=re.S)

def main():
    check='--check' in sys.argv;changed=[]
    for lang,d in DATA.items():
        prefix='' if lang=='en' else lang+'/'
        for tail in ['about.html','index.html']:
            path=ROOT/(prefix+tail);old=path.read_text();text=old
            if tail=='about.html':
                text,n=re.subn(r'<section class="profile-resources quick-facts" id="at-a-glance".*?</section>(?:\s*<section class="profile-resources" id="profile-questions".*?</section>)?',lambda _:section(d),text,count=1,flags=re.S)
                if n!=1:raise ValueError('Missing facts section: '+str(path))
            if tail=='about.html' and lang!='en':text=about_parity(text,lang)
            text=re.sub(r'<script type="application/ld\+json">(.*?)</script>',person_schema,text,flags=re.S)
            from enrich_metadata import enrich
            text=enrich(path,text)[0]
            if text!=old:
                changed.append(str(path.relative_to(ROOT)))
                if not check:
                    if path.read_text()!=old:raise RuntimeError('Concurrent edit')
                    path.write_text(text)
    if check and changed:raise SystemExit('STALE profile facts: '+', '.join(changed))
    print('PASS profile facts: six Person graphs,three dated About facts and six-question HTML sections; '+str(len(changed))+' changes')
if __name__=='__main__':main()
