"""Maintain the carousel hub introduction without changing its published entries.

The frozen carousel renderer inserts gallery entries at galleries:start and
preserves the rest of an existing hub. This source owns only the introduction.
"""
import argparse
import json
import re
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START = '<!-- carousel-intro:start -->'
END = '<!-- carousel-intro:end -->'
LEGACY = '<p>Original English visual explainers by <a href="/about.html" rel="author">Ahmadreza Samadi</a>. Announcement dates and source checks remain explicit.</p>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'carousels/index.html'
    original = path.read_text()
    copy = json.loads((ROOT / 'locales/carousel-hub.json').read_text())['intro_html']
    words = unescape(re.sub(r'<[^>]*>', ' ', copy)).split()
    if not 60 <= len(words) <= 120:
        raise ValueError('Carousel introduction must have 60–120 words')
    if original.count('<!-- galleries:start -->') != 1:
        raise ValueError('Expected the existing gallery entry marker')
    block = START + '\n' + copy + '\n' + END
    if START in original or END in original:
        if original.count(START) != 1 or original.count(END) != 1:
            raise ValueError('Duplicate or incomplete carousel introduction markers')
        updated, count = re.subn(re.escape(START) + r'.*?' + re.escape(END), lambda _: block, original, flags=re.S)
        if count != 1:
            raise ValueError('Malformed carousel introduction markers')
    else:
        if original.count(LEGACY) != 1:
            raise ValueError('Unrecognized carousel introduction; review before replacing')
        updated = original.replace(LEGACY, block, 1)
    if updated != original:
        if args.check:
            raise SystemExit('STALE carousel hub introduction')
        if path.read_text() != original:
            raise RuntimeError('Concurrent carousel hub edit')
        path.write_text(updated)
    print(f'PASS carousel hub introduction: {len(words)} words; existing gallery entries preserved')


if __name__ == '__main__':
    main()
