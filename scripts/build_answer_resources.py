"""Generate and verify the reviewed Markdown companions and their head discovery links."""
import sys
from answer_resources import ROOT, PAGES, machine_head, markdown, mirror_path
from check_internal_links import site_pages

def main():
    check = '--check' in sys.argv
    stale = []
    def record(path, text):
        previous = path.read_text() if path.exists() else None
        if previous != text:
            stale.append(path.relative_to(ROOT).as_posix())
            if not check:
                path.write_text(text)
    for path in site_pages(ROOT):
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text()
        updated = machine_head(source,relative)
        record(path,updated)
        if relative in PAGES:
            record(ROOT / mirror_path(relative),markdown(updated,relative))
    if check and stale:
        raise SystemExit('Machine resources differ: '+', '.join(stale))
    print(f'{len(PAGES)} Markdown companions; {len(stale)} changes')
if __name__ == '__main__':
    main()
