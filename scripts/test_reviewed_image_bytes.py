"""Reviewed output hashes remain strict across different image codec builds."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_share_images as shares
import build_poster_derivatives as posters


class ReviewedImageBytes(unittest.TestCase):
    def exercise(self, module, manifest, corrupt=None):
        config = json.loads((module.ROOT / manifest).read_text())
        config['images'] = config['images'][:1]
        config['preloadPages'] = {}
        row = config['images'][0]
        outputs = ([row['output']] if module is shares else
                   [row[kind]['output'] for kind in ('jpeg', 'webp')])
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory).resolve()
            for name in [row['source'], *outputs]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((module.ROOT / name).read_bytes())
            if corrupt:
                (root / (row['source'] if corrupt == 'source' else outputs[0])).write_bytes(b'changed')
            path = root / manifest
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(config))
            stack.enter_context(patch.object(module, 'ROOT', root))
            if module is posters:
                stack.enter_context(patch.object(module, 'MANIFEST', path))
            stack.enter_context(patch('sys.argv', ['image-check', '--check']))
            renderer = 'build' if module is shares else 'render'
            wrong = b'other encoder bytes' if module is shares else (b'other encoder bytes', row['dimensions'])
            mocked = stack.enter_context(patch.object(module, renderer, return_value=wrong))
            if corrupt:
                with self.assertRaises(ValueError):
                    module.main()
            else:
                module.main()
                mocked.assert_not_called()

    def test_share_preserves_bound_bytes_without_reencoding(self):
        self.exercise(shares, 'locales/share-images.json')

    def test_poster_preserves_bound_bytes_without_reencoding(self):
        self.exercise(posters, 'locales/poster-derivatives.json')

    def test_changed_share_cannot_pass_on_other_encoder(self):
        self.exercise(shares, 'locales/share-images.json', 'output')

    def test_changed_poster_cannot_pass_on_other_encoder(self):
        self.exercise(posters, 'locales/poster-derivatives.json', 'output')

    def test_sources_remain_hash_bound(self):
        for module, manifest in [(shares, 'locales/share-images.json'),
                                 (posters, 'locales/poster-derivatives.json')]:
            with self.subTest(module=module.__name__):
                self.exercise(module, manifest, 'source')


if __name__ == '__main__':
    unittest.main()
