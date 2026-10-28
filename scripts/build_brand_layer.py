"""Build the brand's Ideas/Data destinations and source-driven website sections.

The English home remains the locale layout source. Run build_locales afterwards.
This builder owns only its marked sections, the Known for section and two new pages.
"""
from pathlib import Path
from html import escape as esc
import json
import re
import sys
from enrich_metadata import enrich
from build_analytics import install

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / 'locales/brand-layer.json').read_text())
BASE = 'https://a-samadi.com'
CSS = '<link rel="stylesheet" href="/css/brand-layer.css?v=20261018-brand1">'
CHECK = '--check' in sys.argv
CHANGES = []


def link(url, label):
    return f'<a href="{esc(url, quote=True)}">{esc(label)}</a>'


def store(path, text):
    if path in (ROOT / 'ideas.html', ROOT / 'studies/index.html'):
        text = install(enrich(path, text)[0])
    old = path.read_text() if path.exists() else None
    if old == text:
        return
    CHANGES.append(path.relative_to(ROOT).as_posix())
    if not CHECK:
        if path.exists() and path.read_text() != old:
            raise RuntimeError(f'{path}: concurrent change')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def section(identifier, heading, body):
    return (f'<section class="profile-resources" id="{identifier}" aria-labelledby="{identifier}-title">'
            f'<h2 id="{identifier}-title">{esc(heading)}</h2>{body}</section>')


def marked(text, name, body, before):
    block = f'<!-- {name}:start -->\n{body}\n<!-- {name}:end -->'
    pattern = re.compile(r'<!-- ' + re.escape(name) + r':start -->.*?<!-- ' + re.escape(name) + r':end -->', re.S)
    if pattern.search(text):
        if len(pattern.findall(text)) != 1:
            raise ValueError('Duplicate section ' + name)
        return pattern.sub(lambda _: block, text)
    if text.count(before) != 1:
        raise ValueError('Missing or duplicate insertion point ' + name)
    return text.replace(before, block + '\n' + before, 1)


def styled(text):
    return text if CSS in text else text.replace('</head>', CSS + '\n</head>', 1)


def discovery_footer(text, lang):
    labels = DATA['labels'][lang]
    prefix = '' if lang == 'en' else '/' + lang
    destinations = [prefix + '/#work', prefix + '/about.html', '/studies/', prefix + '/writing/']
    body = '<p class="brand-links">' + ' · '.join(link(url, title) for url, title in zip(destinations, labels['navlabels'])) + '</p>'
    return marked(text, 'brand-discovery-footer', body, '</footer>')


def homepage():
    labels = DATA['labels']['en']
    def card(identifier, title, links):
        return (f'<article class="brand-card" id="{identifier}"><h3>{esc(title)}</h3><ul>' +
                ''.join('<li>' + link(url, label) + '</li>' for url, label in links) + '</ul></article>')
    cards = card('what-i-work-on', 'What I work on', [
        ('/work/appraiva.html', 'AI for property decisions'),
        ('/writing/start-with-the-decision.html', 'Start with the decision'),
        ('/work/royal-abraj.html', 'Building in Dubai')])
    cards += card('property-decision-data', 'Proof', [
        ('/work/appraiva.html', 'Appraiva'), ('/work/royal-abraj.html', 'Royal Abraj Group'),
        ('/studies/', 'Property studies'), ('/studies/#tools', 'Practical tools')])
    cards += card('my-topics', 'My topics', [(topic['path'], topic['labels']['en']) for topic in DATA['identity']['topics']])
    body = (f'<section class="section brand-layer" id="signature-ideas" aria-labelledby="signature-ideas-title">'
            '<div class="section-heading"><h2 id="signature-ideas-title">AI × property × business</h2>'
            '<p>Explore the work, evidence and questions behind my property decisions.</p></div>'
            f'<div class="brand-grid">{cards}</div></section>')
    path = ROOT / 'index.html'
    text = styled(marked(path.read_text(), 'brand-home', body, '<section class="section" id="work">'))
    store(path, discovery_footer(text, 'en'))
    for lang in ('fa', 'ar'):
        path = ROOT / 'locales' / f'{lang}.json'
        translations = json.loads(path.read_text())
        for key in ('ideas', 'intro', 'data', 'studyintro', 'studylink', 'newsletter', 'english'):
            translations[labels[key]] = DATA['labels'][lang][key]
        for english, variants in DATA['homepage_translations'].items():
            translations[english] = variants[0 if lang == 'fa' else 1]
        store(path, json.dumps(translations, ensure_ascii=False, indent=2) + '\n')


def biography():
    for lang in ('en', 'fa', 'ar'):
        labels = DATA['labels'][lang]
        prefix = '' if lang == 'en' else '/' + lang
        path = ROOT / ('' if lang == 'en' else lang) / 'about.html'
        text = path.read_text()
        belief_items = ''.join('<li>' + link(prefix + source, belief) + '</li>'
                               for source, belief in zip(DATA['belief_sources'], labels['beliefitems']))
        beliefs = section('what-i-believe', labels['beliefs'], '<ol>' + belief_items + '</ol>')
        idea_items = ''.join('<li>' + link('/ideas.html#' + idea['id'], idea['name']) + '</li>' for idea in DATA['ideas'])
        ideas = section('signature-ideas', labels['ideas'], '<ul>' + idea_items + '</ul>' + f'<p>{esc(labels["english"])}</p>')
        destinations = ['/studies/', prefix + '/tools/before-you-build-ai.html',
                        '/tools/rental-cash-flow.html', 'https://github.com/ahmadreza-smdi', DATA['newsletter']]
        public = section('work-in-public', labels['public'], '<ul>' + ''.join('<li>' + link(url, title) + '</li>'
                          for url, title in zip(destinations, labels['publiclinks'])) + '</ul>')
        text = marked(text, 'brand-biography', beliefs + ideas + public, '<section class="profile-resources" id="career-timeline"')
        known_links = [prefix + '/work/appraiva.html', prefix + '/tools/before-you-build-ai.html', prefix + '/work/royal-abraj.html']
        known = section('known-for', labels['known'], f'<p>{esc(labels["knownintro"])}</p><ul>' + ''.join(
            f'<li><h3>{link(url, title)}</h3><p>{esc(description)}</p></li>'
            for url, title, description in zip(known_links, labels['knownnames'], labels['knowncopy'])) + '</ul>')
        text, count = re.subn(r'<section class="profile-resources" id="known-for"[^>]*>.*?</section>', lambda _: known, text, flags=re.S)
        if count != 1:
            raise ValueError(f'{path}: Known for section count {count}')
        identity = DATA['identity']
        identity_labels = labels['identitylabels']
        career = section('career-timeline', identity_labels['career'],
                         '<ol>' + ''.join('<li data-career-role="' + key + '"><p>' + esc(copy) + '</p></li>'
                                         for key, copy in zip(('appraiva', 'royal-abraj'), identity['roles'][lang])) +
                         '</ol><ul>' + ''.join('<li>' + esc(copy) + '</li>' for copy in identity['background'][lang]) + '</ul>')
        text, count = re.subn(r'<section class="profile-resources" id="career-timeline"[^>]*>.*?</section>', lambda _: career, text, flags=re.S)
        if count != 1:
            raise ValueError(f'{path}: career section count {count}')
        text, count = re.subn(r'(<section class="profile-resources" id="education"[^>]*>.*?</h2>).*?</section>',
                             lambda m: m[1] + '<p>' + esc(identity_labels['education']) + '</p></section>', text, flags=re.S)
        if count != 1:
            raise ValueError(f'{path}: education section count {count}')
        topic_links = []
        for topic in identity['topics']:
            target = topic['path']
            # The original rent/ownership study is an English resource; translated
            # versions, when present, are selected by the locale-aware source.
            local = ROOT / lang / target.lstrip('/')
            if lang != 'en' and (local / 'index.html' if target.endswith('/') else local).exists():
                target = prefix + target
            topic_links.append('<li>' + link(target, topic['labels'][lang]) + '</li>')
        topics = section('my-topics', identity_labels['topics'], '<ul>' + ''.join(topic_links) + '</ul>')
        text = marked(text, 'brand-biography-topics', topics, '<section class="profile-resources" id="career-timeline"')
        # Name the displayed portrait in each localized biography's schema.
        # The selected image, identity and its existing rights remain unchanged.
        def portrait_metadata(match):
            graph = json.loads(match[1])
            def update_person(value):
                if isinstance(value, dict):
                    if value.get('@type') == 'Person' and value.get('@id') == BASE + '/#person':
                        value['description'] = identity['entity'][lang]
                    for child in value.values():
                        update_person(child)
                elif isinstance(value, list):
                    for child in value:
                        update_person(child)
            update_person(graph)
            for node in graph.get('@graph', [graph]):
                if node.get('@type') == 'ProfilePage':
                    node['image'] = {
                        '@type': 'ImageObject', '@id': BASE + '/#portrait',
                        'url': BASE + '/assets/img/ahmadreza-samadi-hero.jpg',
                        'width': 900, 'height': 1200,
                        'caption': {'en': 'Ahmadreza Samadi in a dark suit',
                                    'fa': 'احمدرضا صمدی با کت‌وشلوار تیره',
                                    'ar': 'أحمدرضا صمدي يرتدي بدلة داكنة'}[lang],
                    }
            return '<script type="application/ld+json">\n' + json.dumps(graph, ensure_ascii=False, indent=2) + '\n</script>'
        text = re.sub(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', portrait_metadata, text, flags=re.S)
        store(path, styled(discovery_footer(text, lang)))


def document(path, title, description, body, nodes):
    url = BASE + path
    page_type = 'CollectionPage' if path == '/studies/' else 'WebPage'
    page = {'@type': page_type, '@id': url + '#page', 'url': url, 'name': title,
            'description': description, 'inLanguage': 'en', 'isPartOf': {'@id': BASE + '/#website'},
            'author': {'@id': BASE + '/#person'}}
    schema = json.dumps({'@context': 'https://schema.org', '@graph': [page, *nodes]}, ensure_ascii=False, indent=2)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)} | Ahmadreza Samadi</title><meta name="description" content="{esc(description, quote=True)}">'
            f'<meta name="author" content="Ahmadreza Samadi"><link rel="canonical" href="{url}">'
            '<link rel="stylesheet" href="/css/site.css?v=20261009-lagoon4-ask1">' + CSS +
            f'<script type="application/ld+json">{schema}</script>'
            f'<meta property="og:title" content="{esc(title, quote=True)}"><meta property="og:type" content="website">'
            f'<meta property="og:url" content="{url}"><meta property="og:description" content="{esc(description, quote=True)}">'
            '<meta property="og:image" content="https://a-samadi.com/assets/img/ahmadreza-samadi-og.jpg">'
            '<meta name="twitter:card" content="summary_large_image"></head><body class="editorial-body">'
            '<a class="skip-link" href="#main">Skip to content</a><header class="editorial-header">'
            '<a href="/">Ahmadreza Samadi / Home</a></header><main class="editorial" id="main">'
            f'<h1>{esc(title)}</h1><p class="lead">{esc(description)}</p>{body}'
            '<footer class="editorial-footer"><a href="/about.html">About Ahmadreza Samadi</a> · '
            '<a href="/ideas.html">Signature ideas</a> · <a href="/studies/">Property Decision Data</a> · '
            f'{link(DATA["newsletter"], "Start with the Decision newsletter")}</footer></main></body></html>\n')


def ideas_page():
    sections, terms = [], []
    for idea in DATA['ideas']:
        diagram = ('<figure class="brand-diagram"><ol>' + ''.join(f'<li>{esc(step)}</li>' for step in idea['steps']) +
                   f'</ol><figcaption>A decision workflow for {esc(idea["name"].lower())}</figcaption></figure>')
        body = (f'<p class="lead">{esc(idea["definition"])}</p><h3>Why it matters</h3><p>{esc(idea["why"])}</p>' + diagram +
                '<h3>Where I apply it</h3><ul>' + ''.join('<li>' + link(url, title) + '</li>' for url, title in idea['apply']) +
                '</ul><h3>Use it tomorrow</h3><ol>' + ''.join(f'<li>{esc(item)}</li>' for item in idea['checklist']) + '</ol>')
        sections.append(section(idea['id'], idea['name'], body))
        terms.append({'@type': 'DefinedTerm', '@id': BASE + '/ideas.html#' + idea['id'], 'name': idea['name'],
                      'description': idea['definition'], 'url': BASE + '/ideas.html#' + idea['id'],
                      'inDefinedTermSet': {'@id': BASE + '/ideas.html#ideas'}, 'creator': {'@id': BASE + '/#person'}})
    term_set = {'@type': 'DefinedTermSet', '@id': BASE + '/ideas.html#ideas', 'name': 'Signature ideas',
                'creator': {'@id': BASE + '/#person'}, 'hasDefinedTerm': [{'@id': t['@id']} for t in terms]}
    store(ROOT / 'ideas.html', document('/ideas.html', 'Signature ideas',
          'Three practical ideas from Ahmadreza Samadi’s essays: start with the decision, define where AI must stop, and count cost per accepted result.',
          '<p>These are the principles I use to explain and design AI workflows. They are supported by the linked essays and tools, rather than claims of measured company results.</p>' + ''.join(sections), [term_set, *terms]))


def studies_page():
    burden = '/studies/rent-burden/' if (ROOT / 'studies/rent-burden/index.html').is_file() else 'https://github.com/ahmadreza-smdi/metro-rent-burden/releases/tag/v1.1.1'
    studies = [('/studies/rent-own-2026/', 'Rent and ownership cash-budget scenarios',
                '2026 edition using ACS 2024 owner-stock values and HUD FY2027 gross rents. Explicit hypothetical budgets retain distinct HUD areas; they are not matched-property yields or observed returns.'),
               (burden, 'Metro rent burden: ACS 2024',
                'Public data, chart, dictionary, workbook and method notes. Compare metropolitan rent pressure with the stated denominator and coverage; this is not a property-level affordability estimate.')]
    body = '<p>Property Decision Data is my series for checking what a housing number can and cannot support. Read the population, geography, source year and assumptions before comparing results.</p>'
    body += ''.join(section('study-' + str(i), title, f'<p>{esc(description)}</p><p>{link(url, "Open the study and methods")}</p>') for i, (url, title, description) in enumerate(studies, 1))
    body += section('tools', 'Apply the evidence', '<ul>' + ''.join('<li>' + link(url, title) + '</li>' for url, title in [('/tools/dubai-purchase-cost.html', 'Dubai purchase-cost calculator'), ('/tools/rental-cash-flow.html', 'Rental cash-flow calculator'), ('/tools/valuation-range.html', 'Valuation range checker'), ('/tools/dubai-rental-yield.html', 'Dubai rental-yield calculator'), ('/tools/before-you-build-ai.html', 'Before you build the AI'), ('/writing/why-rent-to-value-is-not-property-yield.html', 'Why rent divided by home value is not property yield'), ('https://github.com/ahmadreza-smdi', 'Public GitHub repositories')]) + '</ul>')
    body += section('citation', 'How to cite', '<p>Cite Ahmadreza Samadi, the study title, its source-data year and release version, and the exact study or release URL. Keep its methods and limitations with any quoted figure. GitHub releases retain versioned source files and citation information.</p>')
    items = [{'@type': 'ListItem', 'position': i, 'name': title, 'url': url if url.startswith('https:') else BASE + url} for i, (url, title, _) in enumerate(studies, 1)]
    store(ROOT / 'studies/index.html', document('/studies/', 'Property Decision Data',
          'Open property studies by Ahmadreza Samadi, with source years, geography, assumptions, methods and practical decision tools.', body,
          [{'@type': 'ItemList', '@id': BASE + '/studies/#list', 'numberOfItems': len(items), 'itemListElement': items}]))


if __name__ == '__main__':
    homepage()
    biography()
    ideas_page()
    studies_page()
    print(('STALE ' if CHECK and CHANGES else 'PASS ') + 'brand layer: ' + ', '.join(CHANGES or ['no changes needed']))
    if CHECK and CHANGES:
        raise SystemExit(1)
