"""Prepare or check fixed landscape letterboxes of existing approved cover images.

Requires Pillow for this optional local image build. Daily publishing only reads
the saved assets and metadata map; it does not regenerate these images.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent


def build(source, config):
    cover = ImageOps.contain(Image.open(io.BytesIO(source)).convert('RGB'),
                             (config['width'], config['height']), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (config['width'], config['height']), config['background'])
    canvas.paste(cover, ((canvas.width - cover.width) // 2, (canvas.height - cover.height) // 2))
    output = io.BytesIO()
    canvas.save(output, format='PNG', optimize=True)
    if len(output.getvalue()) > config['maximumBytes']:
        canvas = canvas.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        output = io.BytesIO()
        canvas.save(output, format='PNG', optimize=True)
    result = output.getvalue()
    if len(result) > config['maximumBytes']:
        raise ValueError('Share image exceeds the reviewed size limit')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads((ROOT / 'locales/share-images.json').read_text())
    for row in config['images']:
        source, destination = ROOT / row['source'], ROOT / row['output']
        if not source.resolve().is_relative_to(ROOT) or not destination.resolve().is_relative_to(ROOT / 'assets/share') or source == destination:
            raise ValueError('Image paths must retain the original and remain in the public asset tree')
        before = source.read_bytes()
        if hashlib.sha256(before).hexdigest() != row['sourceSha256']:
            raise ValueError('Cover source changed; review it before rebuilding: ' + row['source'])
        result = build(before, config)
        if hashlib.sha256(result).hexdigest() != row['outputSha256']:
            raise ValueError('Rendered bytes differ from the reviewed output: ' + row['output'])
        existing = destination.read_bytes() if destination.exists() else None
        if existing != result:
            if args.check:
                raise SystemExit('STALE share image: ' + row['output'])
            if source.read_bytes() != before or (destination.read_bytes() if destination.exists() else None) != existing:
                raise RuntimeError('Concurrent image change')
            destination.write_bytes(result)
    print(f"PASS share images: {len(config['images'])} original covers preserved; 1200×630, at most 300 KB")


if __name__ == '__main__':
    main()
