"""Plan or apply a guarded navigation complement after a daily helper receipt.

Run after the daily helper's local preparation and before commit/push. The helper
and its immutable manifest remain unchanged. This command adds no Article or
publication permission; it only links an existing complete, receipt-bound family.
An explicit family plan chooses the hub and three related pillars.
"""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
import build_article_hubs as articles
import build_topic_hubs as topics

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = {'.git', '__pycache__', 'node_modules', '.DS_Store'}
CHECKS = [
    ['python3', '-B', 'scripts/check_locale_parity.py'],
    ['python3', '-B', 'scripts/check_internal_links.py'],
    ['node', 'scripts/check_guide_locales.mjs'],
    *[['python3', '-B', 'scripts/' + name, '--check'] for name in (
        'build_feed.py', 'enrich_metadata.py', 'build_llms.py',
        'build_author_boxes.py', 'build_analytics.py', 'build_press.py',
        'build_topic_hubs.py', 'build_status_pages.py', 'build_ask_index.py',
        'build_article_hubs.py')],
    ['python3', '-B', 'scripts/test_check_internal_links.py'],
    ['python3', '-B', 'scripts/test_notify_indexnow.py'],
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(), object_pairs_hook=unique_object)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def inventory(root):
    result = {}
    for parent, dirs, files in os.walk(root):
        if any((Path(parent) / name).is_symlink() for name in dirs if name not in EXCLUDED):
            raise ValueError('Symlink directory requires review: ' + str(parent))
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
        for name in sorted(files):
            path = Path(parent) / name
            if name in EXCLUDED:
                continue
            if path.is_symlink():
                raise ValueError('Symlink requires review: ' + str(path))
            result[path.relative_to(root).as_posix()] = sha(path)
    return result


def checked_relative(value):
    if not isinstance(value, str) or value.startswith('/') or '..' in Path(value).parts:
        raise ValueError('Unsafe receipt path')
    return value


def repo_state(ignore_owned_temporary=None):
    def git(*arguments):
        return subprocess.check_output(['git', *arguments], cwd=ROOT, text=True).rstrip('\n')
    index = Path(git('rev-parse', '--git-path', 'index'))
    if not index.is_absolute():
        index = ROOT / index
    porcelain = git('status', '--porcelain=v1', '--untracked-files=all')
    if ignore_owned_temporary is not None:
        porcelain = '\n'.join(line for line in porcelain.splitlines()
                              if line != '?? ' + ignore_owned_temporary)
    return {'head': git('rev-parse', 'HEAD'), 'index_sha256': sha(index), 'porcelain': porcelain}


def outside_status(state, relative):
    # Public paths in this transaction contain no spaces or rename destinations.
    # Preserve the exact status of every path except our current narrow write.
    return [line for line in state['porcelain'].splitlines() if line[3:] != relative]


def propose(plan, receipt):
    family = plan['family']
    slug = family['stem']
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError('Unsafe family slug')
    if family.get('classification') not in {'core', 'explainer'}:
        raise ValueError('An explicit core/explainer classification is required')
    paths = {lang: articles.prefix(lang) + 'writing/' + slug + '.html'
             for lang in ('en', 'fa', 'ar')}
    if family.get('paths') != paths:
        raise ValueError('Explicit paths must name one matching EN/FA/AR family')
    if receipt.get('status') not in {'prepared-locally-not-published', 'private-preflight-passed'}:
        raise ValueError('A local, uncommitted daily-helper receipt is required')
    if receipt.get('slug') != slug or receipt.get('automatic_daily_exception') is not True:
        raise ValueError('Receipt does not bind this automatic daily family')
    if any(receipt.get(key) is not False for key in ('committed', 'pushed', 'liveVerified')):
        raise ValueError('Sync must precede commit and push')
    if receipt.get('baseHead') != repo_state()['head']:
        raise ValueError('HEAD changed after the daily helper; re-review before syncing')
    owned = receipt.get('ownedHashes', {})
    if set(receipt.get('changed', [])) != set(owned) or not set(paths.values()) <= set(owned):
        raise ValueError('Receipt omits the complete family or its changed-file hashes')
    for relative, digest in owned.items():
        checked_relative(relative)
        source = ROOT / relative
        if not source.is_file() or sha(source) != digest:
            raise ValueError('Daily-helper receipt hash changed: ' + relative)
    data = read_json(ROOT / 'locales/article-hubs.json')
    topic_data = read_json(ROOT / 'locales/topic-hubs.json')
    if any(row['stem'] == slug for row in data['families']):
        raise ValueError('Family is already registered; never duplicate a sync')
    old_paths = {path for row in data['families'] for path in row['paths'].values()}
    if articles.all_articles() != old_paths | set(paths.values()):
        raise ValueError('Inventory is incomplete or includes another unregistered family')
    hub = next((row for row in topic_data['hubs'] if row['id'] == family['hub']), None)
    if hub is None or not hub.get('all_articles_heading'):
        raise ValueError('Unknown or unsupported hub')
    for lang, relative in paths.items():
        articles.resource(relative)
        text = (ROOT / relative).read_text()
        if articles.START in text or articles.END in text:
            raise ValueError('New family already has navigation; review its existing content')
    # Confirm current generated hub output before replacing it with a complement.
    for lang, relative in hub['paths'].items():
        if (ROOT / relative).read_text() != topics.enrich_follow(topics.render(topic_data, hub, lang)):
            raise ValueError('Existing hub differs from its source: ' + relative)
    key = 'article_' + slug.replace('-', '_')
    if key in topic_data['resources'] or any(
            row.get('paths', {}) == paths for row in topic_data['resources'].values()):
        raise ValueError('Resource key or paths already exist; reconcile explicitly')
    topic_data['resources'][key] = {'paths': paths}
    # Keep all existing resource order; put the new Article before trailing films/tools.
    article_positions = [index for index, resource in enumerate(hub['ordered_resources'])
                         if topic_data['resources'][resource]['paths']['en'].startswith('writing/')]
    if not article_positions:
        raise ValueError('Hub has no established Article order')
    hub['ordered_resources'].insert(max(article_positions) + 1, key)
    hub.setdefault('additional_resources', []).append(key)
    data['families'].append(family)
    result = {
        'locales/article-hubs.json': encoded(data),
        'locales/topic-hubs.json': encoded(topic_data),
    }
    for lang, relative in paths.items():
        before = (ROOT / relative).read_text()
        after = articles.install(before, articles.render(family, lang, topic_data['hubs']))
        restored = re.sub(re.escape(articles.START) + r'.*?' + re.escape(articles.END) + r'\n?',
                          '', after, count=1, flags=re.S)
        if restored != before or before.split('<body', 1)[0] != after.split('<body', 1)[0]:
            raise ValueError('Article content, head or dates changed outside navigation')
        result[relative] = after
    for lang, relative in hub['paths'].items():
        result[relative] = topics.enrich_follow(topics.render(topic_data, hub, lang))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family-plan', type=Path, required=True)
    parser.add_argument('--release-receipt', type=Path, required=True)
    parser.add_argument('--record-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Apply only the verified complement; never publish')
    args = parser.parse_args()
    record = args.record_dir.resolve()
    if record.exists() or record.is_relative_to(ROOT):
        raise ValueError('Use a fresh record directory outside the website')
    inputs = {str(p.resolve()): sha(p) for p in (args.family_plan, args.release_receipt)}
    git_before = repo_state()
    before = inventory(ROOT)
    changes = propose(read_json(args.family_plan), read_json(args.release_receipt))
    record.mkdir(parents=True)
    stage = record / 'Staged-Website'
    shutil.copytree(ROOT, stage, ignore=shutil.ignore_patterns(*EXCLUDED))
    for relative, text in changes.items():
        (stage / relative).write_text(text)
    staged_before_checks = inventory(stage)
    expected_outputs = {p: sha(stage / p) for p in changes}
    results = []
    for command in CHECKS:
        run = subprocess.run(command, cwd=stage, text=True, capture_output=True)
        results.append({'command': command, 'exit_code': run.returncode,
                        'stdout': run.stdout, 'stderr': run.stderr})
    (record / 'Checks.json').write_text(encoded({'all_passed': all(x['exit_code'] == 0 for x in results),
                                               'count': len(results), 'results': results}))
    if any(x['exit_code'] for x in results):
        raise RuntimeError('Staged sync checks failed; no website files changed')
    if inventory(stage) != staged_before_checks:
        raise RuntimeError('Staged files changed during checks; no website files changed')
    if (any(sha(Path(p)) != digest for p, digest in inputs.items())
            or inventory(ROOT) != before or repo_state() != git_before):
        raise RuntimeError('Inputs or website changed during preparation; no website files changed')
    rows = [{'path': p, 'before_sha256': before[p], 'after_sha256': expected_outputs[p]} for p in sorted(changes)]
    receipt = {'status': 'checked-private-plan', 'planned_at_utc': datetime.now(timezone.utc).isoformat(),
               'inputs': inputs, 'changes': rows, 'checks': len(results),
               'publication': False, 'human_fact_check_performed': False,
               'native_human_review_performed': False, 'parent_helper_receipt_unchanged': True}
    patch = ''.join(''.join(difflib.unified_diff((ROOT / p).read_text().splitlines(keepends=True),
                    (stage / p).read_text().splitlines(keepends=True), fromfile='a/' + p, tofile='b/' + p))
                    for p in sorted(changes))
    (record / 'navigation-complement.patch').write_text(patch)
    (record / 'Receipt.json').write_text(encoded(receipt))
    if not args.apply:
        print('PASS: checked navigation complement; no website files changed')
        return
    backup = record / 'Before-Apply.zip'
    with zipfile.ZipFile(backup, 'w', zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(changes):
            archive.write(ROOT / p, p)
    with zipfile.ZipFile(backup) as archive:
        if (archive.testzip() is not None or sorted(archive.namelist()) != sorted(changes)
                or any(hashlib.sha256(archive.read(row['path'])).hexdigest() != row['before_sha256']
                       for row in rows)):
            raise RuntimeError('Backup verification failed; no website files changed')
    backup_sha256 = sha(backup)
    expected = dict(before)
    expected_git = git_before
    written = []
    receipt.update(status='applying-navigation-complement', written=written,
                   backup_sha256=backup_sha256, write_intent=None)
    (record / 'Receipt.json').write_text(encoded(receipt))
    for row in rows:
        if (inventory(ROOT) != expected or repo_state() != expected_git
                or inventory(stage) != staged_before_checks
                or sha(backup) != backup_sha256
                or any(sha(Path(p)) != digest for p, digest in inputs.items())):
            raise RuntimeError('Concurrent edit during apply; consult backup and partial receipt')
        receipt['write_intent'] = row
        (record / 'Receipt.json').write_text(encoded(receipt))
        target = ROOT / row['path']
        fd, temporary = tempfile.mkstemp(prefix='.hub-sync-', dir=target.parent)
        os.close(fd)
        try:
            shutil.copyfile(stage / row['path'], temporary)
            shutil.copymode(target, temporary)
            if (sha(target) != row['before_sha256'] or sha(Path(temporary)) != row['after_sha256']
                    or repo_state(Path(temporary).relative_to(ROOT).as_posix()) != expected_git):
                raise RuntimeError('Concurrent target change; refusing replacement')
            os.replace(temporary, target)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()
        expected[row['path']] = row['after_sha256']
        written.append(row['path'])
        current_git = repo_state()
        if (current_git['head'] != git_before['head']
                or current_git['index_sha256'] != git_before['index_sha256']
                or outside_status(current_git, row['path']) != outside_status(expected_git, row['path'])):
            receipt.update(status='interrupted-concurrent-Git-change', written=written,
                           backup_sha256=backup_sha256)
            (record / 'Receipt.json').write_text(encoded(receipt))
            raise RuntimeError('Unrelated Git state changed during apply; consult recovery receipt')
        expected_git = current_git
        receipt.update(status='applying-navigation-complement', written=written,
                       backup_sha256=backup_sha256, write_intent=None)
        (record / 'Receipt.json').write_text(encoded(receipt))
    if inventory(ROOT) != expected or repo_state() != expected_git:
        raise RuntimeError('Unexpected final file change; consult recovery receipt')
    receipt.update(status='applied-locally-not-published', applied_at_utc=datetime.now(timezone.utc).isoformat())
    (record / 'Receipt.json').write_text(encoded(receipt))
    print('PASS: applied guarded navigation complement; no commit or push')


if __name__ == '__main__':
    main()
