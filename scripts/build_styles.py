"""Combine the three authored style layers into one cache-versioned request."""
from pathlib import Path
import re
root = Path(__file__).resolve().parent.parent
sources = ['premium.css', 'editorial.css', 'refinement.css']
css = '\n'.join((root / 'css' / name).read_text() for name in sources)
css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
css = re.sub(r'\s+', ' ', css)
css = re.sub(r'\s*([{};])\s*', r'\1', css).strip()
(root / 'css' / 'site.css').write_text(css + '\n')
print(f'Built css/site.css ({len(css):,} bytes)')
