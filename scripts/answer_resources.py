"""Machine-readable companions to existing public HTML. No network or third-party dependencies."""
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from seo_document import Document, Element, public_url, nodes
from readiness import MODULES, refine_record, semantics

ROOT = Path(__file__).resolve().parents[1]
PAGES = tuple(json.loads((ROOT / 'locales/markdown-pages.json').read_text()))
REVISIONS = {path: revision['modified'] for revision in json.loads((ROOT / 'locales/page-revisions.json').read_text())
             for path in revision['paths']}
PERSON = 'https://a-samadi.com/#person'
PORTRAIT = 'https://a-samadi.com/assets/img/ahmadreza-samadi-hero.jpg'
DESCRIPTION = 'Dubai-based technology entrepreneur who builds AI as Co-Founder & Technical Lead of Appraiva and runs Royal Abraj Group as Co-Founder & CEO.'
NAME = 'Ahmadreza Samadi'
MARKDOWN_LINK = re.compile(r'<link rel="alternate" type="text/markdown" href="[^"]+"\s*/?>')
SCHEMA = re.compile(r'(<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)', re.S)
BLOCKS = set('address article aside blockquote dd details div dl dt fieldset figcaption figure form legend label h1 h2 h3 h4 h5 h6 header li main ol p pre section summary table tbody td th thead tr ul'.split())
SKIP = set('script style template noscript nav footer button input select textarea svg canvas video audio iframe'.split())
def mirror_path(path):
    return Path(path).with_suffix('.md').as_posix()

def machine_head(text, path):
    """Merge the same identifying evidence into every typed declaration. Bare IDs are references."""
    def upgrade(match):
        graph = json.loads(match[2])
        changed = False
        for node in list(nodes(graph)):
            if refine_record(node,path):
                changed = True
            page_url = public_url(path)
            identifier = node.get('@id', '')
            if (path in REVISIONS and node.get('@type') in ('WebPage','CollectionPage','ProfilePage','ItemPage','AboutPage')
                    and isinstance(identifier, str) and identifier.partition('#')[0] == page_url
                    and node.get('dateModified') != REVISIONS[path]):
                node['dateModified'] = REVISIONS[path]
                changed = True
            if node.get('@id') != PERSON or node.get('@type') != 'Person':
                continue
            image = node.get('image', {})
            if not isinstance(image, dict) or image.get('url') not in (None, PORTRAIT):
                raise ValueError(f'{path}: conflicting portrait')
            # Photo identity is independent of ownership or reuse terms.
            fields = {'@type':'ImageObject','@id':'https://a-samadi.com/#portrait','url':PORTRAIT,
                      'contentUrl':PORTRAIT,'name':NAME,'caption':'Ahmadreza Samadi in a dark suit',
                      'width':900,'height':1200}
            if any(image.get(k) != v for k,v in fields.items()) or node.get('disambiguatingDescription') != DESCRIPTION:
                node['image'] = {**image, **fields}
                node['disambiguatingDescription'] = DESCRIPTION
                changed = True
        if not changed:
            return match[0]
        value = json.dumps(graph, ensure_ascii=False, indent=2)
        return match[1]+'\n'+value+'\n'+match[3]
    head, sep, body = text.partition('</head>')
    if not sep:
        return text
    head = SCHEMA.sub(upgrade, head)
    if path in PAGES:
        link = f'<link rel="alternate" type="text/markdown" href="/{mirror_path(path)}">'
        if MARKDOWN_LINK.search(head):
            head = MARKDOWN_LINK.sub(link, head)
        else:
            head += link+'\n'
    else:
        head = MARKDOWN_LINK.sub('', head) if MARKDOWN_LINK.search(head) else head
    return semantics(head+sep+body,path)

def markdown(text, path):
    """Transcribe main-content blocks and inline links. Exclude private-scope operator material."""
    document = Document(text)
    roots = document.tags('main')
    if len(roots) != 1:
        raise ValueError(f'{path}: expected one main element')
    url = public_url(path)
    lines = []
    def inline(node):
        if isinstance(node,str):
            return node
        if node.tag in SKIP or 'hidden' in node.attrs or node.get('aria-hidden') == 'true' or MODULES.intersection(node.get('class').split()):
            return ''
        label = ''.join(inline(ch) for ch in node.children)
        if node.tag == 'a' and label.strip() and node.get('href'):
            dest = urljoin(url,node.get('href'))
            if dest.startswith(('https://','mailto:')):
                return '['+label.strip()+']('+dest.replace(' ','%20').replace(')','%29')+')'
        if node.tag == 'br':
            return ' '
        return label
    def emit(text, prefix=''):
        value = ' '.join(text.split())
        if value:
            lines.append(prefix+value)
    def visit(node):
        if node.tag in SKIP or 'hidden' in node.attrs or node.get('aria-hidden') == 'true' or MODULES.intersection(node.get('class').split()):
            return
        if node.get('aria-labelledby') == 'raia-title':
            return
        if node.tag == 'p' and path.endswith('about.html') and any(el.tag == 'a' and ('#raia-title' in el.get('href') or 'build-ai-run-a-business.html' in el.get('href')) for el in descendants(node)):
            return
        if path.endswith('work/royal-abraj.html') and node.get('class') == 'lead':
            return
        if node.tag.startswith('h') and node.tag[1:].isdigit():
            emit(inline(node), '#' * int(node.tag[1:])+' ')
            return
        buf = []
        prefix = '- ' if node.tag == 'li' else ''
        skip_operator = False
        for child in node.children:
            if path == 'writing/build-ai-run-a-business.html' and isinstance(child,Element):
                if child.tag == 'h2':
                    skip_operator = child.get('id') == 'operator'
                if skip_operator:
                    continue
            if isinstance(child,Element) and child.tag in BLOCKS:
                emit(''.join(buf),prefix);buf.clear()
                visit(child)
            else:
                buf.append(inline(child))
        emit(''.join(buf),prefix)
    visit(roots[0])
    return '\n\n'.join(lines)+'\n'

def descendants(node):
    for child in node.children:
        if isinstance(child,Element):
            yield child
            yield from descendants(child)
