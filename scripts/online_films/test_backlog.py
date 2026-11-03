"""The nine-row exception never grants ordinary publishing or implicit approval."""
from contextlib import ExitStack
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import backlog as b


class BacklogGuards(unittest.TestCase):
    def setUp(self):
        self.root = b.core.ROOT
        self.authority = b.core.read(self.root / b.AUTHORITY)
        self.films = b.core.read(self.root / 'scripts/online_films/schedule.json')
        self.carousels = b.core.read(self.root / 'scripts/online_films/carousels.json')
        self.now = datetime(2026, 11, 3, 23, tzinfo=b.core.ZONE)

    def approved_fixture(self):
        # Synthetic test data, never written to the publication authority.
        return dict(self.authority, status='APPROVED', owner_quote='TEST FIXTURE ONLY',
                    owner_instruction_at='2026-11-03T13:00:00+03:30',
                    not_before='2026-11-03T22:00:00+03:30', expires_at='2026-11-03T23:30:00+03:30')

    def test_exact_nine_scope_and_sorted_original_dates(self):
        items = b.validate_scope(self.authority, self.films, self.carousels)
        self.assertEqual(len(items), 9)
        self.assertEqual(sum(i['kind'] == 'film' for i in items), 5)
        self.assertEqual([i['publish_at'] for i in items], sorted(i['publish_at'] for i in items))

    def test_changed_authority_row_hash_or_destination_rejected(self):
        for field, value in [('sha256', '0' * 64), ('asset_id', 1), ('publish_at', '2026-11-04T21:00:00+03:30'), ('slug', 'other')]:
            bad = copy.deepcopy(self.authority)
            bad['items'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                b.validate_scope(bad, self.films, self.carousels)
        bad = copy.deepcopy(self.films)
        bad['films'][-1]['asset_id'] += 1
        with self.assertRaises(ValueError):
            b.validate_scope(self.authority, bad, self.carousels)
        with self.assertRaises(ValueError):
            b.validate_scope(dict(self.authority, destination='https://other.test'), self.films, self.carousels)

    def test_draft_cannot_reach_network_preparation_or_publication(self):
        with patch.object(b, 'APPROVED_AUTHORITY_SHA256', None), patch.object(b.core, 'run', side_effect=AssertionError('must not execute')), patch.object(b, 'private_checkout', side_effect=AssertionError('must not prepare')):
            with self.assertRaisesRegex(ValueError, 'publication disabled'):
                b.run_backlog(self.root)

    def test_bound_authority_bytes_and_consumed_marker(self):
        authority = self.approved_fixture()
        raw = json.dumps(authority).encode()
        with tempfile.TemporaryDirectory() as td, patch.object(b, 'APPROVED_AUTHORITY_SHA256', b.digest(raw)):
            root = Path(td)
            b.require_approval(raw, authority, self.now, root)
            for changed_raw, changed_obj in [(raw+b' ', authority), (raw, dict(authority, owner_quote='Changed'))]:
                with self.assertRaises(ValueError):
                    b.require_approval(changed_raw, changed_obj, self.now, root)
            (root / b.CONSUMED).parent.mkdir(parents=True)
            (root / b.CONSUMED).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'already consumed'):
                b.require_approval(raw, authority, self.now, root)

    def test_absolute_window_and_all_protected_slots(self):
        authority = self.approved_fixture()
        for now in [self.now-timedelta(days=1), self.now+timedelta(hours=1)]:
            with self.assertRaises(ValueError): b.safe_window(authority, now)
        broad = dict(authority, not_before='2026-11-03T00:00:00+03:30', expires_at='2026-11-03T23:59:59+03:30', owner_instruction_at='2026-11-02T23:00:00+03:30')
        for hour in (10, 12, 18, 21):
            for minutes in (-30, 0, 30):
                with self.subTest(hour=hour, minutes=minutes), self.assertRaises(ValueError):
                    b.safe_window(broad, self.now.replace(hour=hour, minute=0)+timedelta(minutes=minutes))
        b.safe_window(broad, self.now.replace(hour=14))
        with self.assertRaises(ValueError): b.safe_window(dict(broad, not_before='2026-11-03T00:00:00'), self.now)

    def test_verify_dispatch_must_be_successful_same_commit_and_exact_step(self):
        run = dict(head_sha='base', event='workflow_dispatch', status='completed', conclusion='success', path='.github/workflows/scheduled-films.yml')
        jobs = {'jobs':[{'steps':[{'name':b.VERIFY_STEP, 'conclusion':'success'}]}]}
        b.verify_run_evidence(run, jobs, 'base')
        for field, value in [('head_sha','other'), ('event','schedule'), ('status','in_progress'), ('conclusion','failure'), ('path','other.yml')]:
            with self.subTest(field=field), self.assertRaises(ValueError): b.verify_run_evidence(dict(run, **{field:value}), jobs, 'base')
        with self.assertRaises(ValueError): b.verify_run_evidence(run, {'jobs':[]}, 'base')

    def test_partial_existing_publication_rejected(self):
        item = self.authority['items'][0]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.assertFalse(b.existing_publication(root,item,{}))
            page=root/('writing/'+item['slug']+'.html');page.parent.mkdir();page.write_text('partial')
            with self.assertRaisesRegex(ValueError, 'Partial existing'):
                b.existing_publication(root,item,{})

    def test_git_index_is_checked_against_reviewed_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'page.html').write_text('reviewed')
            subprocess.run(['git','add','page.html'],cwd=root,check=True)
            expected={'page.html':b.digest(b'reviewed')}
            b.verify_git_bytes(root,expected)
            (root/'page.html').write_text('concurrent change')
            subprocess.run(['git','add','page.html'],cwd=root,check=True)
            with self.assertRaisesRegex(ValueError,'content differs'):
                b.verify_git_bytes(root,expected)

    def test_only_verified_existing_media_can_be_skipped(self):
        item = self.authority['items'][0]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);slug=item['slug'];review={'media':{'film':'film','cover':'cover'},'files':{}}
            for p in [f'writing/{slug}.html',f'fa/writing/{slug}.html',f'ar/writing/{slug}.html',f'watch/{slug}.html']:
                target=root/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('published')
            for key,name in [('film','film.mp4'),('cover','cover.png')]:
                target=root/f'assets/writing/{slug}/{name}';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(key.encode());review['files'][key]=b.core.sha(target)
            b.core.write(root/f"data/film-publications/{item['key']}.json",dict(slug=slug,bundle_sha256=item['sha256'],scheduled_at=item['publish_at']))
            self.assertTrue(b.existing_publication(root,item,review))
            (root/f'assets/writing/{slug}/film.mp4').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'immutable media differs'):b.existing_publication(root,item,review)

    def test_cli_rejects_mixed_modes_without_entering_publishers(self):
        for flags in [['--verify-backlog-2026-11-03','--wait-for-slot'], ['--owner-catchup-2026-11-03','--verify'], ['--backlog-verification-run','123']]:
            with patch('sys.argv',['publish.py',*flags]), patch.object(b.core,'read',side_effect=AssertionError('must not read schedule')), self.assertRaises(SystemExit):
                b.core.main()

    def test_private_rehearsal_and_concurrent_main_never_copy_or_push(self):
        for mode in ('verify', 'concurrent', 'expired', 'success'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td, ExitStack() as stack:
                root=Path(td)/'source';root.mkdir()
                for name in [b.ASSETS,'scripts/online_films/schedule.json','scripts/online_films/carousels.json']:
                    target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(self.root/name,target)
                authority=self.approved_fixture();raw=json.dumps(authority).encode();(root/b.AUTHORITY).write_bytes(raw)
                clock=[self.now];actions=[];staged=[]
                class Clock(datetime):
                    @classmethod
                    def now(cls, zone=None):return clock[0]
                def run(args,*unused):
                    actions.append(args)
                    if args[:2]==['git','rev-parse']:return 'other' if args[-1]=='origin/main' and mode=='concurrent' else 'base'
                    if args[:2]==['git','add']:staged[:]=args[3:]
                    if args==['git','diff','--cached','--name-only']:return '\n'.join(staged)
                    return ''
                def obtain(config,item,area,local):return area, {'slug':item['slug'],'public_allowlist':['writing/'+item['slug']+'.html']}
                def prepare(site,folder,review,*unused,**options):
                    self.assertTrue(options.get('backlog_discovery'))
                    path=site/('writing/'+review['slug']+'.html');path.parent.mkdir(exist_ok=True);path.write_text('private')
                def checks(site,*unused):
                    self.assertFalse((root/'writing').exists())
                    if mode=='expired':clock[0]+=timedelta(days=1)
                    return []
                for obj,name,value in [(b,'APPROVED_AUTHORITY_SHA256',b.digest(raw)),(b,'datetime',Clock),
                        (b,'private_checkout',lambda src,dst,base:shutil.copytree(src,dst)),(b,'apply_seo',lambda *a:None),
                        (b,'release_checks',checks),(b,'check_discovery',lambda *a:{}),(b,'require_verify_dispatch',lambda *a:None),
                        (b,'verify_derivatives',lambda *a:None),(b,'verify_git_bytes',lambda *a:None),
                        (b.core,'run',run),(b.core,'obtain',obtain),
                        (b.carousel,'obtain',obtain),(b.core,'prepare',prepare),(b.carousel,'prepare',prepare),
                        (b.carousel,'verify_live',lambda *a:None)]:stack.enter_context(patch.object(obj,name,value))
                if mode in ('concurrent','expired'):
                    with self.assertRaises(ValueError):b.run_backlog(root,verification_run_id='123')
                else:b.run_backlog(root,verify=mode=='verify',verification_run_id=None if mode=='verify' else '123')
                pushes=[a for a in actions if a[:2]==['git','push']]
                self.assertEqual(len(pushes),int(mode=='success'))
                notifications=[a for a in actions if 'scripts/notify_indexnow.py' in a]
                self.assertEqual(len(notifications),int(mode=='success'))
                self.assertEqual((root/b.CONSUMED).exists(),mode=='success')
                self.assertEqual((root/'writing').exists(),mode=='success')
                if mode=='success':
                    marker=b.core.read(root/b.CONSUMED)
                    self.assertNotIn('checks',marker)
                    self.assertEqual(marker['id'],b.IDENTIFIER)
                    self.assertEqual(marker['authority_sha256'],b.digest(raw))
                    with self.assertRaisesRegex(ValueError,'already consumed'):b.run_backlog(root,verification_run_id='123')


if __name__ == '__main__':
    unittest.main()
