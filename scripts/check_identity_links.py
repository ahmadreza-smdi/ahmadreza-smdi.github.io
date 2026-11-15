"""Read-only checks for reviewed identity links and language-scoped name forms."""
from pathlib import Path
import json
import re
from check_internal_links import site_pages, protected
from check_brand import BAD_NAME
from seo_document import Document, nodes
from identity_links import verified_profiles, profile_key

ROOT = Path(__file__).resolve().parents[1]
NATIVE = re.compile(r'(?:أ?احمد|أحمد)\s*[‌ ]?رضا\s+صمد[يیى]|(?:احمد|أحمد)\s+صمد[يیى]')

def name_issues(value, language):
    issues = []
    if BAD_NAME.search(value) or re.search(r'\bAhmed\b', value, re.I):
        issues.append('incorrect-name-form')
    if language == 'en' and NATIVE.search(value):
        issues.append('native-name-outside-localized-content')
    return issues

def check_html(raw, path, expected):
    doc = Document(raw)
    language = path.split('/')[0] if path.startswith(('fa/', 'ar/')) else 'en'
    own = {profile_key(u) for u in expected}
    issues = []
    for a in doc.tags('a'):
        if profile_key(a.get('href')) in own and 'me' not in a.get('rel').lower().split():
            issues.append('own-profile-missing-rel-me: ' + a.get('href'))
    for block in doc.blocks():
        data = json.loads(block)
        issues += name_issues(block, language)
        for node in nodes(data):
            if node.get('@type') == 'Person' and node.get('@id') == 'https://a-samadi.com/#person':
                if 'sameAs' in node and (not isinstance(node['sameAs'], list) or sorted(node['sameAs']) != sorted(expected)):
                    issues.append('sameAs-differs-from-reviewed-profiles')
                if 'alternateName' in node and node['alternateName'] != ['Ahmad Samadi']:
                    issues.append('incorrect-canonical-alternateName')
    return issues

def scoped_strings(value, language='en'):
    if isinstance(value, dict):
        language = value.get('language', value.get('inLanguage', language))
        for key, item in value.items():
            yield from scoped_strings(item, key if key in ('en', 'fa', 'ar') else language)
    elif isinstance(value, list):
        for item in value:
            yield from scoped_strings(item, language)
    elif isinstance(value, str):
        yield value, language

def audit(root=ROOT):
    expected = verified_profiles(); issues = []; count = 0
    for path in site_pages(root):
        rel = path.relative_to(root).as_posix(); count += 1
        issues += [(rel, message) for message in check_html(path.read_text(), rel, expected)]
    machine = [root/'llms.txt', root/'llms-full.txt', root/'ask-index.json']
    machine += [path.with_suffix('.md') for path in site_pages(root)]
    # Only public mirrors: repository documentation is not a public biography.
    for path in sorted(set(machine)):
        if not path.is_file() or protected(path.relative_to(root)): continue
        rel = path.relative_to(root).as_posix(); language = rel.split('/')[0] if rel.startswith(('fa/','ar/')) else 'en'
        if path.suffix == '.json':
            values = scoped_strings(json.loads(path.read_text()), language)
        else:
            values = [(path.read_text(), language)]
        for value, lang in values:
            issues += [(rel, message) for message in name_issues(value, lang)]
    return count, sorted(set(issues))

if __name__ == '__main__':
    count, issues = audit()
    for path, issue in issues: print('FAIL', path, issue)
    print(f'{"FAIL" if issues else "PASS"} identity links: {count} HTML pages, reviewed sameAs and scoped machine names; {len(issues)} issues')
    raise SystemExit(bool(issues))
