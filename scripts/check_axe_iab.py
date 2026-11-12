"""Run axe in the owner's in-app browser on loopback; check a matching private receipt offline."""
import argparse
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import unquote, urlsplit

from check_internal_links import protected

ROOT = Path(__file__).resolve().parents[1]
VERSION = "4.10.3"
LIBRARY_SHA = "880970c081707360e64f34cea25ff91892f5bc95675b0776925b9709dd8a68bb"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"]
SAMPLE = ROOT / "scripts/fixtures/axe-template-sample.txt"
EXT = set(".html .css .js .mjs .json .csv .webp .png .jpg .jpeg .avif .gif .svg .ico .woff2 .woff .mp4 .webm .vtt .webmanifest".split())


def inputs():
    sample = [p for p in SAMPLE.read_text().splitlines() if p and not p.startswith("#")]
    if not sample or len(sample) != len(set(sample)):
        raise ValueError("missing or duplicate template samples")
    # The published manifest bounds file access. Read working bytes to catch edits before release.
    names = subprocess.check_output(["git", "ls-tree", "-rz", "--name-only", "origin/site"], cwd=ROOT).decode().split("\0")
    assets = {}
    for name in filter(None, names):
        f = ROOT / name
        if protected(name) or f.suffix.lower() not in EXT or name.split("/")[0] in {"docs", "scripts"}: continue
        if name.startswith(".") or f.resolve() != f or not f.is_file(): continue
        assets[name] = f
    if set(sample) - assets.keys(): raise ValueError("a sample page is missing from the site")
    digest = sha256()
    for name,f in sorted(assets.items()):
        # Large media also affect the browser sample; hash incrementally.
        h = sha256()
        with f.open("rb") as stream:
            for block in iter(lambda: stream.read(1024*1024), b""): h.update(block)
        digest.update(name.encode()+b"\0"+h.digest())
    return sample,assets,digest.hexdigest()


def required_widget(path):
    if path.endswith(("studies/rent-own-2026/index.html", "studies/rent-own-2026/embed.html")):
        return "rent-own-study"
    if path in {
        "tools/dubai-purchase-cost.html", "tools/embed/dubai-purchase-cost.html",
        "tools/rental-cash-flow.html", "tools/embed/rental-cash-flow.html",
    }:
        return "property-calculator"
    return None


def verify(doc, sample, fingerprint):
    if not isinstance(doc,dict) or doc.get("format") != 2 or doc.get("axe") != VERSION or doc.get("tags") != TAGS or doc.get("inputs") != fingerprint:
        raise ValueError("receipt has stale inputs, wrong rule scope or wrong axe version")
    rows = doc.get("results")
    if not isinstance(rows,list) or len(rows)!=len(sample) or any(not isinstance(r,dict) for r in rows):
        raise ValueError("incomplete sample")
    if set(r.get("path") for r in rows) != set(sample): raise ValueError("missing, unexpected or duplicate sample")
    for r in rows:
        if (r.get("error") or not isinstance(r.get("passes"),list) or not r["passes"] or
            not isinstance(r.get("violations"),list) or not isinstance(r.get("incomplete"),list) or r.get("version") != VERSION):
            raise ValueError("incomplete axe result: "+str(r.get("path")))
        expected = required_widget(r['path'])
        if expected and r.get('initializedWidget') != expected:
            raise ValueError(f"{r['path']}: the interactive content did not initialize")
        if r["violations"]: raise ValueError(f"{r['path']}: axe violations: {r['violations']}")
    return sum(len(r['incomplete']) for r in rows)


def serve(sample, assets, fingerprint, library):
    if sha256(library).hexdigest() != LIBRARY_SHA: raise ValueError("unexpected axe-core library SHA-256")
    widgets = {path: required_widget(path) for path in sample if required_widget(path)}
    cfg=json.dumps(dict(sample=sample,inputs=fingerprint,tags=TAGS,version=VERSION,widgets=widgets))
    page=(ROOT/"scripts/fixtures/axe-iab-runner.tmpl").read_text().replace("/*AUDIT_CONFIG*/null",cfg).encode()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':return self.send_error(403)
            name=unquote(urlsplit(self.path).path).lstrip('/')
            if name=='__qa/': data,mime=page,'text/html; charset=utf-8'
            elif name=='__qa/axe.js': data,mime=library,'application/javascript'
            else:
                if not name or name.endswith('/'):name+='index.html'
                if name not in assets:return self.send_error(404)
                data = assets[name].read_bytes()
                mime = 'text/javascript' if name.endswith('.mjs') else mimetypes.guess_type(name)[0] or 'application/octet-stream'
                if name in sample:
                    marker=b'</body>';inject=b'<script src="/__qa/axe.js"></script>'
                    if marker not in data:return self.send_error(422)
                    data=data.replace(marker,inject+marker,1)
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
            self.send_header('Content-Security-Policy',"default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; form-action 'none'")
            self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def log_message(self,*args):pass
    with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
        server.timeout=1
        print(f"Open http://127.0.0.1:{server.server_port}/__qa/ in the in-app browser. Stop with Ctrl-C. Expires in 10 minutes.",flush=True)
        end=time.monotonic()+600
        while time.monotonic()<end:server.handle_request()


def main():
    ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group()
    g.add_argument('--serve-local',type=Path,metavar='PINNED_AXE_JS');g.add_argument('--receipt',type=Path)
    a=ap.parse_args();receipt=a.receipt or os.environ.get('WEBSITE_AXE_RECEIPT')
    if not a.serve_local and not receipt:print('SKIP: no fresh in-app browser axe receipt supplied');return 0
    try:
        sample,assets,fp=inputs()
        if a.serve_local:serve(sample,assets,fp,a.serve_local.read_bytes());return 0
        manual=verify(json.loads(Path(receipt).read_text()),sample,fp)
        print(f'PASS: {len(sample)} pages scanned; no automatic violations; {manual} rule/page items require review');return 0
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as e:print(f'FAIL: {e}');return 1
    except KeyboardInterrupt:return 0

if __name__=='__main__':raise SystemExit(main())
