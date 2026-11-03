"""Read-only, hash-bound title guard for new English CollectionPage galleries.

The Article-family guard remains unchanged. This separate mode requires an actual
private preparation receipt, checks every new HTML path, and also checks titles
on changed existing pages. It grants no publication or factual-review authority.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from check_new_article_titles import HeadTitle, absolute_path, git, read_regular, unique_object

ROOT = Path(__file__).absolute().parents[1]


def check(root, receipt_path):
    root = absolute_path(root)
    receipt_path = absolute_path(receipt_path)
    receipt_bytes = read_regular(receipt_path)
    receipt = json.loads(receipt_bytes, object_pairs_hook=unique_object)
    if (receipt.get('status') != 'prepared-locally-not-published'
            or receipt.get('kind') != 'carousel_gallery_batch'
            or any(receipt.get(k) is not False for k in ['committed', 'pushed', 'liveVerified'])):
        raise ValueError('An unpublished gallery preparation receipt is required')
    if Path(git(root, 'rev-parse', '--show-toplevel').decode()) != root:
        raise ValueError('Root must be the repository top level')
    head = git(root, 'rev-parse', 'HEAD').decode()
    if receipt.get('baseHead') != head:
        raise ValueError('Stale preparation baseHead')
    hashes = receipt.get('galleryHashes')
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError('Exact new gallery hashes required')
    for relative, digest in hashes.items():
        if (not re.fullmatch(r'carousels/[a-z0-9]+(?:-[a-z0-9]+)*\.html', relative)
                or relative == 'carousels/index.html'
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ValueError('Unsafe gallery declaration')
    tracked = set(git(root, 'ls-tree', '-r', '--name-only', 'HEAD').decode().splitlines())
    changed = set(git(root, 'diff', '--name-only', 'HEAD', '--', '*.html').decode().splitlines())
    untracked = set(git(root, 'ls-files', '--others', '--exclude-standard', '--', '*.html').decode().splitlines())
    new_paths = (changed | untracked) - tracked
    if new_paths != set(hashes):
        raise ValueError('Receipt must cover all and only new HTML galleries')
    snapshots = {}
    lengths = {}
    for relative in sorted(changed | untracked):
        data = read_regular(root / relative)
        snapshots[relative] = data
        source = data.decode('utf-8')
        if relative in hashes:
            if hashlib.sha256(data).hexdigest() != hashes[relative]:
                raise ValueError('Prepared gallery bytes changed: ' + relative)
            blocks = re.findall(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', source, re.S)
            nodes = []
            for raw in blocks:
                block = json.loads(raw, object_pairs_hook=unique_object)
                nodes.extend(block.get('@graph', [block]) if isinstance(block, dict) else block)
            canonical = 'https://a-samadi.com/' + relative
            galleries = [n for n in nodes if isinstance(n, dict) and n.get('@type') == 'CollectionPage' and n.get('@id') == canonical + '#gallery' and n.get('url') == canonical]
            if len(galleries) != 1:
                raise ValueError('Exactly one matching gallery CollectionPage required')
        elif re.search(r'<meta\b[^>]*name=[\"\']robots[\"\'][^>]*content=[\"\'][^\"\']*noindex', source, re.I):
            continue
        parser = HeadTitle()
        parser.feed(source)
        parser.close()
        route = relative[:-10] if relative.endswith('index.html') else relative
        lengths[relative] = parser.checked_length('https://a-samadi.com/' + route, max_length=65)
    if (git(root, 'rev-parse', 'HEAD').decode() != head
            or read_regular(receipt_path) != receipt_bytes
            or set(git(root, 'diff', '--name-only', 'HEAD', '--', '*.html').decode().splitlines()) != changed
            or set(git(root, 'ls-files', '--others', '--exclude-standard', '--', '*.html').decode().splitlines()) != untracked
            or any(read_regular(root / p) != data for p, data in snapshots.items())):
        raise ValueError('Preparation, HEAD or HTML changed during checking')
    return lengths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        lengths = check(args.root, args.receipt)
    except (ValueError, OSError, UnicodeError, subprocess.CalledProcessError, AssertionError) as error:
        print('FAIL: carousel title check: ' + str(error), file=sys.stderr)
        return 1
    print(f'PASS carousel and changed-page titles: {len(lengths)} pages; limit65; no files changed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
