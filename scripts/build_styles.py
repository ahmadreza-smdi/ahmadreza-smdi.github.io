"""Combine the three authored style layers into one cache-versioned request."""
from pathlib import Path
import re
import sys
root = Path(__file__).resolve().parent.parent
sources = ['premium.css', 'editorial.css', 'refinement.css']
css = '\n'.join((root / 'css' / name).read_text() for name in sources)
css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
css = re.sub(r'\s+', ' ', css)
css = re.sub(r'\s*([{};])\s*', r'\1', css).strip()
destination = root / 'css' / 'site.css'
if '--check' in sys.argv:
    if destination.read_text() != css + '\n':
        raise SystemExit('FAIL: css/site.css differs from its three source layers')
    print('PASS combined stylesheet')
    raise SystemExit(0)
destination.write_text(css + '\n')
print(f'Built css/site.css ({len(css):,} bytes)')
