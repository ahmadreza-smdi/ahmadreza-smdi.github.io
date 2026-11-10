"""Apply reviewed translation parity patches to otherwise hand-authored pages.

Each replacement records its English source. Unexpected or duplicate source
copy fails closed so future editing cannot silently overwrite a new revision.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def restore(text, replacements):
    for row in replacements:
        before, after = row['before'], row['after']
        if text.count(after) == 1:
            continue
        if text.count(before) != 1:
            raise ValueError('Reviewed source is missing or duplicated: ' + row['source'])
        text = text.replace(before, after, 1)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data = json.loads((ROOT / 'locales/translation-restorations.json').read_text())
    changed = []
    for relative, replacements in data.items():
        path = ROOT / relative
        if not path.resolve().is_relative_to(ROOT) or not relative.startswith(('fa/', 'ar/')):
            raise ValueError('Restorations must target existing localized pages')
        old = path.read_text()
        new = restore(old, replacements)
        if new == old:
            continue
        changed.append(relative)
        if not args.check:
            if path.read_text() != old:
                raise RuntimeError('Concurrent change: ' + relative)
            path.write_text(new)
    if args.check and changed:
        raise SystemExit('STALE translation restorations: ' + ', '.join(changed))
    print(f'PASS translation restorations: {len(data)} pages; {len(changed)} changes')


if __name__ == '__main__':
    main()
