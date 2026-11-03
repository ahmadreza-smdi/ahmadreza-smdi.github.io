"""Private rehearsal and one-use publication of the exact reviewed SEO backlog.

Normal scheduled publishers do not enter this module. The checked-in draft
authority is deliberately unusable for publication until an actual owner quote,
bounded window and its reviewed byte hash are recorded together.
"""
from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import urllib.request
from xml.etree import ElementTree as ET

import publish as core
import publish_carousel as carousel

IDENTIFIER = 'catchup-backlog-2026-11-03'
AUTHORITY = 'scripts/online_films/catchup-2026-11-03.json'
ASSETS = 'scripts/online_films/catchup-2026-11-03-assets.json'
CONSUMED = 'data/catchup-publications/2026-11-03.json'
ITEMS_SHA256 = 'f3ad211a0834d549690ee092099a530ca8e45fe243f57023d9c72348f70bc6b3'
ASSETS_SHA256 = '79709a9e8256516175982c53f4ddf0c2a507fb9895e52229417e2e450caac1f1'
# Populate only with the byte hash of the actual, explicitly approved authority.
APPROVED_AUTHORITY_SHA256 = '846f94e8391a18f2e3a5809778be3c6bde5d91e1d5cc684d1442ffab75acd0b5'
VERIFY_STEP = 'Rehearse the exact nine-item backlog privately'
FIELDS = {'schema', 'id', 'destination', 'action', 'single_use', 'status',
          'owner_quote', 'owner_instruction_at', 'not_before', 'expires_at',
          'assets_sha256', 'items'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def items_digest(items):
    return digest(json.dumps(items, sort_keys=True, separators=(',', ':')).encode())


def validate_scope(authority, film_config, carousel_config):
    if (set(authority) != FIELDS or authority['schema'] != 1
            or authority['id'] != IDENTIFIER
            or authority['destination'] != 'https://a-samadi.com'
            or authority['action'] != 'publish_exact_missed_backlog_once'
            or authority['single_use'] is not True
            or authority['assets_sha256'] != ASSETS_SHA256
            or items_digest(authority['items']) != ITEMS_SHA256):
        raise ValueError('Exact backlog scope or asset binding differs')
    core.validate_schedule(film_config)
    carousel.validate(carousel_config)
    for config in (film_config, carousel_config):
        if (config['repository'] != 'ahmadreza-smdi/ahmadreza-smdi.github.io'
                or config['site_url'] != 'https://a-samadi.com'):
            raise ValueError('Backlog destination changed')
    for item in authority['items']:
        kind = item['kind']
        config, collection = ((film_config, 'films') if kind == 'film'
                              else (carousel_config, 'carousels'))
        matches = [row for row in config[collection] if row['key'] == item['key']]
        expected = {k: v for k, v in item.items()
                    if k != 'kind' and not (kind == 'film' and k == 'slug')}
        if matches != [expected]:
            raise ValueError('Scheduled row differs: ' + kind + ' ' + item['key'])
    return authority['items']


def safe_window(authority, now):
    """Require the approved absolute window and all four protected slot margins."""
    moments = [datetime.fromisoformat(authority[key])
               for key in ('owner_instruction_at', 'not_before', 'expires_at')]
    if any(moment.utcoffset() != timedelta(hours=3, minutes=30) for moment in moments):
        raise ValueError('Approval and window require explicit Tehran offset')
    instruction, start, end = moments
    latest_slot = max(datetime.fromisoformat(row['publish_at'])
                      for row in authority['items'])
    if not (instruction <= start < end <= start + timedelta(days=1)
            and start > latest_slot + timedelta(minutes=30)
            and start <= now <= end):
        raise ValueError('Catch-up is early, expired or outside its approved window')
    local = now.astimezone(core.ZONE)
    for hour in (10, 12, 18, 21):
        slot = local.replace(hour=hour, minute=0, second=0, microsecond=0)
        if abs((local - slot).total_seconds()) <= 1800:
            raise ValueError('Protected publishing window')


def require_approval(raw, authority, now, root):
    if (not APPROVED_AUTHORITY_SHA256 or digest(raw) != APPROVED_AUTHORITY_SHA256
            or json.loads(raw) != authority
            or authority['status'] != 'APPROVED'
            or not isinstance(authority['owner_quote'], str)
            or not authority['owner_quote'].strip()):
        raise ValueError('Owner approval missing or authority bytes changed; publication disabled')
    safe_window(authority, now)
    if (root / CONSUMED).exists():
        raise ValueError('This one-use backlog authority is already consumed')


def verify_run_evidence(run, jobs, base):
    if (run.get('head_sha') != base or run.get('event') != 'workflow_dispatch'
            or run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or run.get('path') != '.github/workflows/scheduled-films.yml'):
        raise ValueError('A successful verify dispatch on the exact current commit is required')
    steps = [step for job in jobs.get('jobs', []) for step in job.get('steps', [])
             if step.get('name') == VERIFY_STEP and step.get('conclusion') == 'success']
    if len(steps) != 1:
        raise ValueError('Verify dispatch did not complete the exact backlog rehearsal')


def require_verify_dispatch(config, run_id, base):
    if not re.fullmatch(r'[1-9][0-9]*', str(run_id or '')):
        raise ValueError('Supply the successful verification run ID')
    endpoint = f"repos/{config['repository']}/actions/runs/{run_id}"
    run = json.loads(core.run(['gh', 'api', endpoint]))
    jobs = json.loads(core.run(['gh', 'api', endpoint + '/jobs?per_page=100']))
    verify_run_evidence(run, jobs, base)


def existing_publication(root, item, review):
    kind, slug = item['kind'], item['slug']
    receipt_path = root / f"data/{kind}-publications/{item['key']}.json"
    pages = ([f'writing/{slug}.html', f'fa/writing/{slug}.html',
              f'ar/writing/{slug}.html', f'watch/{slug}.html'] if kind == 'film'
             else [f'carousels/{slug}.html'])
    present = [bool((root / name).exists()) for name in pages]
    if not receipt_path.exists() and not any(present):
        return False
    if not receipt_path.is_file() or not all(present):
        raise ValueError('Partial existing publication; reconcile before catch-up: ' + slug)
    receipt = core.read(receipt_path)
    expected = {'slug': slug, 'bundle_sha256': item['sha256'],
                'scheduled_at': item['publish_at']}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('Existing publication receipt differs: ' + slug)
    if kind == 'film':
        media = {f'assets/writing/{slug}/film.mp4': review['media']['film'],
                 f'assets/writing/{slug}/cover.png': review['media']['cover']}
    else:
        media = {f'assets/carousels/{slug}/slide-{i + 1:02d}.png': name
                 for i, name in enumerate(review['media']['slides'])}
        media[f'assets/carousels/{slug}/carousel.pdf'] = review['media']['pdf']
    for destination, member in media.items():
        if core.sha(root / destination) != review['files'][member]:
            raise ValueError('Existing immutable media differs: ' + destination)
    return True


def insert_bound_entry(config, row, identity):
    matches = [existing for existing in config['images']
               if existing[identity] == row[identity]]
    if matches and matches != [row]:
        raise ValueError('Existing reviewed image entry differs: ' + row[identity])
    if not matches:
        config['images'].append(row)


def apply_seo(site, assets):
    shares = core.read(site / 'locales/share-images.json')
    posters = core.read(site / 'locales/poster-derivatives.json')
    hubs = core.read(site / 'locales/article-hubs.json')
    for item in assets['items']:
        share = item['share']
        if core.sha(site / share['source']) != share['sourceSha256']:
            raise ValueError('Frozen artwork differs: ' + share['source'])
        insert_bound_entry(shares, share, 'source')
        if item['kind'] == 'film':
            insert_bound_entry(posters, item['poster'], 'source')
            families = [family for family in hubs['families'] if family['stem'] == item['slug']]
            if len(families) != 1:
                raise ValueError('Exact new film article family missing')
            families[0]['watch'] = 'watch/' + item['slug'] + '.html'
    for path, data in [('share-images', shares), ('poster-derivatives', posters), ('article-hubs', hubs)]:
        core.write(site / ('locales/' + path + '.json'), data)
    for name in ('build_share_images', 'build_poster_derivatives', 'build_article_hubs',
                 'build_carousel_hub', 'enrich_metadata', 'build_feed', 'build_llms',
                 'build_ask_index', 'build_analytics', 'build_status_pages'):
        core.run(['python3', '-B', 'scripts/' + name + '.py'], site)


def release_checks(site, title_receipts=()):
    commands = '''python3 -B scripts/check_locale_parity.py
python3 -B scripts/check_internal_links.py
python3 -B scripts/check_new_article_titles.py
python3 -B scripts/test_check_internal_links.py
python3 -B scripts/test_notify_indexnow.py
python3 -B scripts/test_build_author_boxes.py
python3 -B scripts/test_build_llms_public_resources.py
python3 -B scripts/test_build_llms_catalogues.py
python3 -B scripts/test_metadata_completeness.py
python3 -B scripts/test_locale_restorations.py
python3 -B scripts/test_calculator_embed_links.py
python3 -B scripts/enrich_metadata.py --check
python3 -B scripts/build_author_boxes.py --check
python3 -B scripts/build_analytics.py --check
python3 -B scripts/build_feed.py --check
python3 -B scripts/build_llms.py --check
python3 -B scripts/build_ask_index.py --check
python3 -B scripts/build_press.py --check
python3 -B scripts/build_topic_hubs.py --check
python3 -B scripts/build_calculator_embeds.py --check
python3 -B scripts/build_status_pages.py --check
python3 -B scripts/build_profile_facts.py --check
python3 -B scripts/build_article_hubs.py --check
python3 -B scripts/build_rent_study_locales.py --check
python3 -B scripts/enrich_study_metadata.py --check
python3 -B scripts/build_brand_layer.py --check
python3 -B scripts/follow_blocks.py --check
python3 -B scripts/build_share_images.py --check
python3 -B scripts/build_locale_restorations.py --check
node scripts/check_guide_locales.mjs
node scripts/test_rent_study_locales.mjs
git diff --check
python3 -B scripts/check_internal_links.py --check-orphans
python3 -B -m unittest discover -s scripts/online_films -p test_*.py
node scripts/test_valuation_range.cjs
python3 -B scripts/test_check_new_article_titles.py
python3 -B scripts/build_poster_derivatives.py --check
python3 -B scripts/build_carousel_hub.py --check
node --check js/future.js'''.splitlines()
    commands.append('python3 -B scripts/test_content_discovery.py')
    if title_receipts:
        # New film families are checked with their actual preparation receipts,
        # as required by the existing title checker. The no-receipt maintenance
        # mode deliberately rejects new HTML, so it is not used for this batch.
        position = commands.index('python3 -B scripts/check_new_article_titles.py')
        commands[position:position + 1] = [shlex.join([
            'python3', '-B', 'scripts/check_new_article_titles.py', '--release-receipt', str(receipt)
        ]) for receipt in title_receipts]
    results = []
    for command in commands:
        output = core.run(shlex.split(command), site)
        results.append({'command': command, 'output': output, 'status': 'PASS'})
    spec = importlib.util.spec_from_file_location('backlog_title_check', site / 'scripts/check_new_article_titles.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    count = 0
    for loc in ET.parse(site / 'sitemap.xml').findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
        url = loc.text
        relative = url.removeprefix('https://a-samadi.com/')
        path = site / (relative + 'index.html' if not relative or relative.endswith('/') else relative)
        parser = checker.HeadTitle()
        parser.feed(path.read_text()); parser.close()
        parser.checked_length(url, max_length=65)
        count += 1
    results.append({'command': 'HeadTitle: every canonical sitemap page, including new galleries/watch pages',
                    'status': 'PASS', 'output': f'{count} canonical titles validated'})
    return results


def check_discovery(site, items):
    expected = set()
    for item in items:
        slug = item['slug']
        expected.update(['https://a-samadi.com/writing/' + slug + '.html',
                         'https://a-samadi.com/watch/' + slug + '.html']
                        if item['kind'] == 'film' else
                        ['https://a-samadi.com/carousels/' + slug + '.html'])
    sitemap = ET.parse(site / 'sitemap.xml')
    sitemap_urls = {n.text for n in sitemap.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
    feed = ET.parse(site / 'writing/feed.xml')
    feed_urls = {n.text for n in feed.findall('./channel/item/link')}
    feed_urls.update(n.get('href') for n in feed.findall('.//{http://www.w3.org/2005/Atom}link')
                     if n.get('rel') == 'related')
    ask_urls = {n['url'] for n in core.read(site / 'ask-index.json')['published_resources']}
    llms_urls = set(re.findall(r'\]\((https://a-samadi\.com/[^)]+)\)', (site / 'llms.txt').read_text()))
    for name, urls in [('sitemap.xml', sitemap_urls), ('writing/feed.xml', feed_urls),
                       ('ask-index.json', ask_urls), ('llms.txt', llms_urls)]:
        if expected - urls:
            raise ValueError('Backlog discovery missing from ' + name + ': ' + str(sorted(expected - urls)))
    return {'required_urls': sorted(expected), 'files': ['sitemap.xml', 'writing/feed.xml', 'ask-index.json', 'llms.txt']}


def verify_derivatives(config, root, paths):
    for relative in paths:
        if not relative.endswith(('.jpg', '.webp')):
            continue
        request = urllib.request.Request(config['site_url'] + '/' + relative,
                                         headers={'User-Agent': 'Ahmadreza-backlog-release-verifier/1.0'})
        with urllib.request.urlopen(request, timeout=90) as response:
            received = response.read()
        if received != (root / relative).read_bytes():
            raise RuntimeError('Live poster derivative mismatch: ' + relative)


def verify_git_bytes(root, expected, revision=''):
    """Bind the Git index/commit itself to the privately tested output bytes."""
    for name, expected_sha in expected.items():
        data = subprocess.check_output(['git', 'show', revision + ':' + name], cwd=root)
        if digest(data) != expected_sha:
            raise ValueError('Concurrent staged/committed content differs: ' + name)


def private_checkout(root, destination, base):
    # Independent Git index/refs; no local commit and no mutation of the source
    # checkout. Existing objects are read through Git's local shared-clone path.
    core.run(['git', 'clone', '--shared', '--no-checkout', str(root), str(destination)], root)
    shutil.copytree(root, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*core.EXCLUDE))
    core.run(['git', 'read-tree', base], destination)


def run_backlog(root=core.ROOT, *, verify=False, local_bundles=None,
                verification_run_id=None, report_path=None):
    root = Path(root).resolve()
    raw = (root / AUTHORITY).read_bytes()
    authority = json.loads(raw)
    film_config = core.read(root / 'scripts/online_films/schedule.json')
    carousel_config = core.read(root / 'scripts/online_films/carousels.json')
    items = validate_scope(authority, film_config, carousel_config)
    if core.sha(root / ASSETS) != ASSETS_SHA256:
        raise ValueError('Backlog artwork manifest changed')
    assets = core.read(root / ASSETS)
    if not verify:
        require_approval(raw, authority, datetime.now(core.ZONE), root)
        if local_bundles or report_path:
            raise ValueError('Live catch-up requires exact remote bundles alone')
        if core.run(['git', 'status', '--porcelain=v1', '--untracked-files=all'], root):
            raise ValueError('Catch-up requires a clean dedicated checkout')
    elif verification_run_id:
        raise ValueError('Rehearsal does not consume a verification run')
    if report_path and Path(report_path).resolve().is_relative_to(root):
        raise ValueError('Private rehearsal report must remain outside the public checkout')
    base = core.run(['git', 'rev-parse', 'HEAD'], root)
    if not verify:
        require_verify_dispatch(film_config, verification_run_id, base)
    original = core.inventory(root)
    stamp = datetime.now(core.ZONE).isoformat(timespec='seconds')
    with tempfile.TemporaryDirectory(prefix='exact-seo-backlog-') as td:
        temp = Path(td).resolve()
        site = temp / 'site'
        private_checkout(root, site, base)
        allowed = {'llms-full.txt', 'ask-index.json', 'locales/share-images.json', 'locales/poster-derivatives.json',
                   'locales/article-hubs.json', 'carousels/index.html'}
        prepared = []
        title_receipts = []
        for item in items:
            print('Private backlog preparation: ' + item['kind'] + ' ' + item['key'], flush=True)
            area = temp / (item['kind'] + '-' + item['key'])
            area.mkdir()
            config, publisher = ((film_config, core) if item['kind'] == 'film'
                                 else (carousel_config, carousel))
            folder, review = publisher.obtain(config, item, area, local_bundles)
            if review['slug'] != item['slug']:
                raise ValueError('Bundle topic differs from exact authority')
            already = existing_publication(root, item, review)
            if not already:
                if item['kind'] == 'film':
                    record = area / 'record'
                    record.mkdir()
                    core.prepare(site, folder, review, stamp, record, backlog_discovery=True)
                    title_receipts.append(record / 'Release-Prepared.json')
                else:
                    carousel.prepare(site, folder, review, stamp, backlog_discovery=True)
            allowed.update(review['public_allowlist'])
            prepared.append({**item, 'already_published': already})
        for item in assets['items']:
            allowed.add(item['share']['output'])
            if item['kind'] == 'film':
                allowed.update(item['poster'][kind]['output'] for kind in ('jpeg', 'webp'))
        apply_seo(site, assets)
        print('Private backlog assets/discovery generated; checking complete batch', flush=True)
        after = core.inventory(site)
        changed = sorted(name for name, value in after.items() if original.get(name) != value)
        if set(original) - set(after) or set(changed) - allowed:
            raise ValueError('Change outside the exact reviewed backlog paths: ' +
                             str(sorted(set(changed) - allowed)))
        discovery = check_discovery(site, items)
        checks = release_checks(site, title_receipts)
        result = {'mode': 'PRIVATE_REHEARSAL' if verify else 'AUTHORIZED_CATCHUP',
                  'base': base, 'content_timestamp': stamp, 'authority_sha256': digest(raw),
                  'source_inventory_sha256': items_digest(original),
                  'items': prepared, 'checks': checks, 'discovery': discovery, 'public_paths': list(changed),
                  'hashes': {name: after[name] for name in changed}}
        if verify:
            if core.inventory(root) != original:
                raise ValueError('Private rehearsal changed the source checkout')
            if report_path:
                core.write(Path(report_path), result)
            print(f'PASS: exact backlog privately rehearsed; {len(checks)} checks; no publication')
            return result
        # All rendering and checks finish privately before any tracked file copy.
        require_approval((root / AUTHORITY).read_bytes(), authority, datetime.now(core.ZONE), root)
        core.run(['git', 'fetch', 'origin', 'main'], root)
        if (core.run(['git', 'rev-parse', 'origin/main'], root) != base
                or core.inventory(root) != original):
            raise ValueError('Concurrent main or checkout edit; review again')
        for item in prepared:
            if item['already_published']:
                continue
            receipt = {'scheduled_at': item['publish_at'], 'content_timestamp': stamp,
                       'slug': item['slug'], 'bundle_sha256': item['sha256'],
                       'public_paths': list(result['public_paths']), 'site_checks_passed': len(checks),
                       'automatic_daily_exception': False,
                       'catch_up_authorization': {'id': IDENTIFIER, 'original_date': item['key'],
                                                 'owner_direct_request': True,
                                                 'evidence_sha256': digest(raw)}}
            path = f"data/{item['kind']}-publications/{item['key']}.json"
            core.write(site / path, receipt)
            changed.append(path)
        # Public one-use receipt contains the release binding, not private
        # rehearsal command output or local temporary paths.
        core.write(site / CONSUMED, {
            'id': IDENTIFIER, 'base': base, 'content_timestamp': stamp,
            'authority_sha256': digest(raw), 'assets_sha256': ASSETS_SHA256,
            'items': prepared, 'site_checks_passed': len(checks),
            'public_paths': list(result['public_paths']), 'hashes': result['hashes'],
            'single_use_consumed': True, 'verification_run_id': str(verification_run_id)
        })
        changed.append(CONSUMED)
        final_hashes = {name: core.sha(site / name) for name in changed}
        for name in sorted(changed):
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(site / name, destination)
        core.run(['git', 'add', '--', *sorted(changed)], root)
        core.run(['git', 'diff', '--cached', '--check'], root)
        if set(core.run(['git', 'diff', '--cached', '--name-only'], root).splitlines()) != set(changed):
            raise ValueError('Unexpected staged paths')
        verify_git_bytes(root, final_hashes)
        # Consumed marker is staged locally now; the approval/window check must
        # not mistake that new local marker for a previously published batch.
        if digest((root / AUTHORITY).read_bytes()) != APPROVED_AUTHORITY_SHA256:
            raise ValueError('Authority changed before commit')
        safe_window(authority, datetime.now(core.ZONE))
        core.run(['git', 'config', 'user.name', 'github-actions[bot]'], root)
        core.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], root)
        core.run(['git', 'commit', '-m', 'Publish exact owner-authorized SEO backlog once'], root)
        commit = core.run(['git', 'rev-parse', 'HEAD'], root)
        if core.run(['git', 'rev-parse', commit + '^'], root) != base:
            raise ValueError('Unexpected commit parent; no push')
        verify_git_bytes(root, final_hashes, commit)
        safe_window(authority, datetime.now(core.ZONE))
        core.run(['git', 'push', 'origin', commit + ':refs/heads/main'], root)
        carousel.verify_live(film_config, commit, changed)
        verify_derivatives(film_config, root, changed)
        # This bot publication has its own exact, already-verified deployment.
        # Notify its changed canonical URLs once as part of this one-use path;
        # private rehearsal and consumed-authority retries cannot reach this.
        indexnow = core.run(['python3', '-B', 'scripts/notify_indexnow.py',
                             '--before', base, '--after', commit], root)
        print(indexnow, flush=True)
        print('Published exact backlog once: ' + commit)
        return {**result, 'commit': commit, 'indexnow': indexnow}
