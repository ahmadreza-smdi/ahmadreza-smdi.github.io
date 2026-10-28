"""Read-only title checks for a daily family or existing-page maintenance.

Run with the actual helper Release-Prepared.json after hub synchronization and
before commit. This checks current titles, not the helper's pre-sync byte hashes.
It grants no publishing authority or human/native review certification. Length
means Unicode code points after HTML entity decoding and whitespace collapse.
Without a receipt, check changed existing indexable pages against 65 characters.
New HTML pages still require the actual daily receipt and the 60-character limit.
"""
import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).absolute().parent.parent


def absolute_path(path):
    if '..' in path.parts:
        raise ValueError('Parent traversal is not permitted')
    return path.absolute()


def open_directory(path):
    """Open each component without following a symlink, including ancestors."""
    path = absolute_path(path)
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_regular(path):
    path = absolute_path(path)
    parent_fd = open_directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=parent_fd)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError('Input must be a regular file')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                return stream.read()
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON keys are not permitted')
        result[key] = value
    return result


def git(root, *arguments):
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1')
    return subprocess.check_output(['git', *arguments], cwd=root, env=environment,
                                   stderr=subprocess.DEVNULL).rstrip(b'\n')


class HeadTitle(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heads = self.head_ends = self.titles = 0
        self.in_head = self.in_title = False
        self.svg_depth = 0
        self.title_parts = []
        self.canonicals = []

    def handle_starttag(self, tag, attrs):
        if self.in_title:
            raise ValueError('Malformed title markup')
        if tag == 'head':
            if self.heads:
                raise ValueError('Exactly one complete head is required')
            self.heads += 1
            self.in_head = True
        elif tag == 'title':
            if not self.in_head and self.svg_depth:
                return  # SVG accessibility text is not the page's head title.
            if not self.in_head or self.titles:
                raise ValueError('Exactly one title inside head is required')
            self.titles += 1
            self.in_title = True
        elif tag == 'svg':
            if self.in_head:
                raise ValueError('SVG content must be outside head')
            self.svg_depth += 1
        elif tag == 'body' and self.in_head:
            raise ValueError('Head must close before body')
        elif tag == 'link':
            values = dict(attrs)
            if any(key == 'rel' and 'canonical' in (value or '').lower().split()
                   for key, value in attrs):
                if not self.in_head or len(values) != len(attrs):
                    raise ValueError('Malformed canonical link')
                self.canonicals.append(values.get('href'))

    def handle_startendtag(self, tag, attrs):
        if tag == 'title' and not self.in_head and self.svg_depth:
            return
        if tag == 'svg':
            if self.in_head:
                raise ValueError('SVG content must be outside head')
            return
        if tag in {'head', 'title'}:
            raise ValueError('Head and title require closing tags')
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'title':
            if not self.in_title:
                if not self.in_head and self.svg_depth:
                    return
                raise ValueError('Malformed title closing tag')
            self.in_title = False
        elif self.in_title:
            raise ValueError('Malformed title markup')
        elif tag == 'head':
            if not self.in_head:
                raise ValueError('Malformed head closing tag')
            self.in_head = False
            self.head_ends += 1
        elif tag == 'svg' and self.svg_depth:
            self.svg_depth -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

    def handle_comment(self, data):
        if self.in_title:
            raise ValueError('Malformed title comment')

    def handle_decl(self, decl):
        if self.in_title:
            raise ValueError('Malformed title declaration')

    def checked_length(self, canonical, max_length=60):
        if (self.heads != 1 or self.head_ends != 1 or self.in_head
                or self.titles != 1 or self.in_title):
            raise ValueError('Exactly one complete head and title are required')
        if self.canonicals != [canonical]:
            raise ValueError('Exactly one matching self-canonical is required')
        title = ' '.join(''.join(self.title_parts).split())
        if not any(not character.isspace()
                   and unicodedata.category(character) not in {'Cc', 'Cf', 'Cs'}
                   for character in title):
            raise ValueError('Title must contain rendered text')
        if len(title) > max_length:
            raise ValueError(f'Title exceeds {max_length} Unicode characters')
        return len(title)


def check(root, receipt_path):
    if receipt_path.name != 'Release-Prepared.json':
        raise ValueError('Use the actual Release-Prepared.json filename')
    receipt_path = absolute_path(receipt_path)
    receipt_bytes = read_regular(receipt_path)
    receipt = json.loads(receipt_bytes.decode('utf-8'), object_pairs_hook=unique_object)
    if not isinstance(receipt, dict):
        raise ValueError('Receipt must be a JSON object')
    if (receipt.get('status') != 'prepared-locally-not-published'
            or receipt.get('automatic_daily_exception') is not True
            or any(receipt.get(key) is not False
                   for key in ('committed', 'pushed', 'liveVerified'))):
        raise ValueError('A live uncommitted automatic daily helper receipt is required')
    slug = receipt.get('slug')
    if not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError('Receipt slug must be a safe lowercase stem')
    paths = {lang: prefix + 'writing/' + slug + '.html'
             for lang, prefix in (('en', ''), ('fa', 'fa/'), ('ar', 'ar/'))}
    owned = receipt.get('ownedHashes')
    if not isinstance(owned, dict) or not set(paths.values()) <= set(owned):
        raise ValueError('Receipt must declare all three exact Article paths')
    for relative, digest in owned.items():
        if (not isinstance(relative, str) or relative.startswith('/')
                or '\\' in relative or '..' in Path(relative).parts
                or relative in {'', '.'} or '\0' in relative
                or Path(relative).as_posix() != relative
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ValueError('Receipt contains an unsafe path or malformed hash declaration')
    root = absolute_path(root)
    root_fd = open_directory(root)
    os.close(root_fd)
    if Path(os.fsdecode(git(root, 'rev-parse', '--show-toplevel'))) != root:
        raise ValueError('Root must be the Git repository top level')
    head = git(root, 'rev-parse', '--verify', 'HEAD').decode('ascii')
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', head) or receipt.get('baseHead') != head:
        raise ValueError('Receipt baseHead is stale or does not match current full HEAD')
    if git(root, 'ls-tree', '-r', '--name-only', '-z', head, '--', *paths.values()):
        raise ValueError('Family paths already exist at base HEAD; historical pages are excluded')
    source_bytes = {}
    lengths = {}
    for lang, relative in paths.items():
        try:
            source_bytes[relative] = read_regular(root / relative)
            parser = HeadTitle()
            parser.feed(source_bytes[relative].decode('utf-8'))
            parser.close()
            lengths[lang] = parser.checked_length('https://a-samadi.com/' + relative)
        except UnicodeError:
            raise ValueError(relative + ': invalid UTF-8') from None
        except OSError:
            raise ValueError(relative + ': missing regular file or unsafe symlink') from None
        except ValueError as error:
            raise ValueError(relative + ': ' + str(error)) from None
        except AssertionError:
            raise ValueError(relative + ': malformed HTML') from None
    if (git(root, 'rev-parse', '--verify', 'HEAD').decode('ascii') != head
            or read_regular(receipt_path) != receipt_bytes
            or any(read_regular(root / relative) != content
                   for relative, content in source_bytes.items())):
        raise ValueError('Receipt, HEAD or new Article bytes changed during checking')
    return lengths


def check_existing(root):
    """Audit local edits without borrowing or fabricating a daily release receipt."""
    head = git(root, 'rev-parse', 'HEAD')
    paths = git(root, 'diff', '--name-only', '-z', 'HEAD', '--', '*.html')
    untracked = git(root, 'ls-files', '--others', '--exclude-standard', '-z', '--', '*.html')
    if untracked:
        raise ValueError('New HTML pages require --release-receipt')
    sources = {}; lengths = {}
    for raw_path in paths.split(b'\0'):
        if not raw_path:
            continue
        relative = raw_path.decode('utf-8')
        try:
            git(root, 'cat-file', '-e', head.decode() + ':' + relative)
        except subprocess.CalledProcessError:
            raise ValueError('New HTML pages require --release-receipt: ' + relative)
        data = read_regular(root / relative)
        sources[relative] = data
        source = data.decode('utf-8')
        if re.search(r'<meta\b[^>]*name=[\"\']robots[\"\'][^>]*content=[\"\'][^\"\']*noindex', source, re.I):
            continue
        parser = HeadTitle(); parser.feed(source); parser.close()
        route = relative[:-10] if relative.endswith('index.html') else relative
        try:
            lengths[relative] = parser.checked_length('https://a-samadi.com/' + route, max_length=65)
        except ValueError as error:
            raise ValueError(relative + ': ' + str(error))
    if (git(root, 'rev-parse', 'HEAD') != head
            or git(root, 'diff', '--name-only', '-z', 'HEAD', '--', '*.html') != paths
            or git(root, 'ls-files', '--others', '--exclude-standard', '-z', '--', '*.html') != untracked
            or any(read_regular(root / path) != data for path, data in sources.items())):
        raise ValueError('HEAD or HTML files changed during checking')
    return lengths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-receipt', type=Path)
    parser.add_argument('--root', type=Path, default=ROOT,
                        help='Website repository top level; defaults to script parent directory')
    args = parser.parse_args()
    try:
        if args.release_receipt is None:
            lengths = check_existing(args.root)
            print(f'PASS: existing-page titles ({len(lengths)} changed indexable pages, limit 65); no files changed')
            return 0
        lengths = check(args.root, args.release_receipt)
    except (ValueError, OSError, UnicodeError, subprocess.CalledProcessError, AssertionError) as error:
        print('FAIL: new daily title check: ' + str(error), file=sys.stderr)
        return 1
    print('PASS: new daily titles (' + ', '.join(lang + ' ' + str(lengths[lang])
          for lang in ('en', 'fa', 'ar')) + ' Unicode characters); no files changed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
