"""Build reviewed, same-size video poster derivatives without changing originals.

The manifest binds each existing source to its derivatives. Video poster
attributes and explicitly reviewed above-fold preloads are managed here;
article dates, share images and video sources stay intact.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
from html import escape

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / 'locales/poster-derivatives.json'
VIDEO = re.compile(r'<video\b[^>]*>', re.I)
POSTER = re.compile(r'\bposter=(?P<quote>[\"\'])(?P<url>[^\"\']+)(?P=quote)', re.I)
PRELOAD = re.compile(r'<link\b[^>]*\bdata-poster-preload(?:=[\"\'][^\"\']*[\"\'])?[^>]*>\n?', re.I)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def render(source, kind, quality):
    with Image.open(io.BytesIO(source)) as original:
        image = original.convert('RGB')
        output = io.BytesIO()
        if kind == 'jpeg':
            image.save(output, format='JPEG', quality=quality, optimize=True, progressive=True)
        else:
            image.save(output, format='WEBP', quality=quality, method=6)
        return output.getvalue(), list(image.size)


def safe_asset(name):
    path = (ROOT / name).resolve()
    if not path.is_relative_to((ROOT / 'assets/writing').resolve()):
        raise ValueError('Poster must remain under assets/writing: ' + name)
    return path


def update_posters(text, mapping):
    def video(match):
        def poster(attr):
            url = attr['url']
            replacement = mapping.get(url)
            return attr[0] if not replacement else f'poster={attr["quote"]}{replacement}{attr["quote"]}'
        return POSTER.sub(poster, match[0])
    return VIDEO.sub(video, text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads(MANIFEST.read_text())
    mapping, originals, changes = {}, {}, []
    for row in config['images']:
        source = safe_asset(row['source'])
        data = source.read_bytes()
        if digest(data) != row['sourceSha256']:
            raise ValueError('Original poster changed; review required: ' + row['source'])
        originals[source] = data
        for kind in ('jpeg', 'webp'):
            spec = row[kind]
            dest = safe_asset(spec['output'])
            if dest == source or dest.parent != source.parent:
                raise ValueError('Derivative must be beside its preserved original')
            old = dest.read_bytes() if dest.exists() else None
            # Keep exact reviewed bytes across platform codec versions. Missing
            # or changed files still require a render matching the bound hash.
            if old is not None and digest(old) == spec['sha256']:
                result = old
                with Image.open(io.BytesIO(result)) as image:
                    dimensions = list(image.size)
            else:
                result, dimensions = render(data, kind, spec.get('quality', config['quality'][kind]))
            if dimensions != row['dimensions'] or digest(result) != spec['sha256']:
                raise ValueError('Derivative differs from reviewed manifest: ' + spec['output'])
            if len(result) > config['maximumBytes']:
                raise ValueError('Poster exceeds size limit: ' + spec['output'])
            if old != result:
                changes.append((dest, old, result))
        mapping['/' + row['source']] = '/' + row['jpeg']['output']

    page_count = 0
    preloads = config.get('preloadPages', {})
    for relative, poster in preloads.items():
        page = (ROOT / relative).resolve()
        if not page.is_relative_to(ROOT) or not page.is_file() or page.suffix != '.html' or poster not in mapping.values():
            raise ValueError('Invalid reviewed poster preload: ' + relative)
    for page in sorted(ROOT.rglob('*.html')):
        if any(p.startswith('.') for p in page.relative_to(ROOT).parts):
            continue
        old = page.read_bytes()
        text = update_posters(old.decode('utf-8'), mapping)
        if len(PRELOAD.findall(text)) > 1:
            raise ValueError('Duplicate poster preloads: ' + str(page))
        text = PRELOAD.sub('', text)
        poster = preloads.get(page.relative_to(ROOT).as_posix())
        if poster:
            videos = [attr['url'] for video in VIDEO.finditer(text) for attr in POSTER.finditer(video[0])]
            if poster not in videos or text.count('</head>') != 1:
                raise ValueError('Preload must match a visible video poster: ' + str(page))
            text = text.replace('</head>', f'<link rel="preload" as="image" href="{escape(poster, quote=True)}" fetchpriority="high" data-poster-preload>\n</head>', 1)
        updated = text.encode('utf-8')
        if old != updated:
            page_count += 1
            changes.append((page, old, updated))

    if args.check and changes:
        for path, _, _ in changes:
            print('STALE ' + str(path.relative_to(ROOT)))
        raise SystemExit(1)
    if not args.check:
        for path, data in originals.items():
            if path.read_bytes() != data:
                raise RuntimeError('Concurrent source edit: ' + str(path))
        for path, old, _ in changes:
            if (path.read_bytes() if path.exists() else None) != old:
                raise RuntimeError('Concurrent file edit: ' + str(path))
        for path, _, data in changes:
            path.write_bytes(data)
    print(f'PASS posters: {len(config["images"])} preserved originals; JPEG/WebP <= '
          f'{config["maximumBytes"]} bytes; {page_count} page updates')


if __name__ == '__main__':
    main()
