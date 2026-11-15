"""Preserve page bytes while marking links to the owner's reviewed profiles."""
from html import unescape
from pathlib import Path
import json
import re
from urllib.parse import urlsplit

REVIEW = Path(__file__).with_name('fixtures') / 'identity-profiles.json'

def verified_profiles():
    data = json.loads(REVIEW.read_text(encoding='utf-8'))
    profiles = [row['url'] for row in data['profiles']]
    if len(profiles) != len(set(profiles)) or not all(row.get('ownership_source') for row in data['profiles']):
        raise ValueError('Duplicate or unreviewed identity profile')
    return profiles

def profile_key(url):
    p = urlsplit(unescape(url))
    if p.scheme not in ('http', 'https') or p.username or p.password:
        return None
    host = (p.hostname or '').lower().removeprefix('www.')
    if host.endswith('.linkedin.com'):
        host = 'linkedin.com'
    path = p.path.rstrip('/')
    if host == 'linkedin.com' and path == '/in/ahmadreza-samadi/ar':
        path = '/in/ahmadreza-samadi'
    return host, path

def add_identity_rel(source, profiles=None):
    own = {profile_key(u) for u in (profiles if profiles is not None else verified_profiles())}
    def edit(match):
        tag = match[0]
        href = re.search(r'\bhref\s*=\s*([\x22\x27])(.*?)\1', tag, re.I | re.S)
        if not href or profile_key(href[2]) not in own:
            return tag
        rel = re.search(r'\brel\s*=\s*([\x22\x27])(.*?)\1', tag, re.I | re.S)
        if rel:
            if 'me' in rel[2].lower().split():
                return tag
            return tag[:rel.start(2)] + rel[2] + (' ' if rel[2] else '') + 'me' + tag[rel.end(2):]
        return tag[:-1] + ' rel="me">'
    return re.sub(r'<a\b[^>]*>', edit, source, flags=re.I)
