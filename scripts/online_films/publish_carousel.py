"""Release one reviewed English carousel gallery at10:00Tehran through the existing workflow."""
from pathlib import Path
from datetime import datetime,timedelta,date
import argparse,importlib.util,json,os,re,shutil,tempfile,time,urllib.request,zipfile
import publish as core
ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'scripts/online_films/carousels.json'
CATCHUP=ROOT/'scripts/online_films/carousel-catchup-2026-10-28.json'

def owner_catchup_rows(config,now,authorization):
 """One explicit same-day owner exception; never a general late-release switch."""
 rows=[r for r in config['carousels'] if r['key']=='2026-10-28']
 if len(rows)!=1:raise ValueError('Exact catch-up row missing')
 row=rows[0]
 expected={'owner_instruction_date':'2026-10-28','key':row['key'],'slug':row['slug'],'bundle_sha256':row['sha256'],'destination':'https://a-samadi.com','action':'publish_missed_carousel_once','not_before':'2026-10-28T10:30:01+03:30','expires_at':'2026-10-28T23:30:00+03:30'}
 if authorization!=expected:raise ValueError('Exact owner catch-up authorization differs')
 if not datetime.fromisoformat(expected['not_before'])<=now<=datetime.fromisoformat(expected['expires_at']):raise ValueError('Owner catch-up expired or early')
 return rows

def validate(config):
 if config.get('schema')!=1 or config.get('timezone')!='Asia/Tehran' or config.get('daily_count')!=1 or config.get('local_slot')!='10:00':raise ValueError('Carousel cadence changed')
 dates=[];slugs=[]
 for row in config['carousels']:
  due=datetime.fromisoformat(row['publish_at'])
  if due.utcoffset()!=timedelta(hours=3,minutes=30) or due.strftime('%H:%M:%S')!='10:00:00':raise ValueError('Wrong carousel slot/timezone')
  if row['key']!=due.date().isoformat() or not re.fullmatch(r'[0-9a-f]{64}',row['sha256']):raise ValueError('Invalid date/hash')
  if not re.fullmatch(r'tech-trend-[a-z0-9-]+',row['slug']):raise ValueError('Unsafe carousel slug')
  if not isinstance(row['asset_id'],int) or row['asset_id']<=0:raise ValueError('Invalid release asset ID')
  if Path(row['asset_name']).name!=row['asset_name']:raise ValueError('Unsafe asset name')
  dates.append(row['key']);slugs.append(row['slug'])
 if dates!=sorted(set(dates)) or len(slugs)!=len(set(slugs)):raise ValueError('At most one carousel per day; no duplicate family')

def rows_now(config,now,prewarm=False):
 rows=config['carousels'];due=core.due_rows({'films':rows},now)
 if due:return due
 if prewarm:
  return [r for r in rows if datetime.fromisoformat(r['publish_at']).date()==now.astimezone(core.ZONE).date() and 0<(datetime.fromisoformat(r['publish_at'])-now).total_seconds()<=10800]
 return []

def unpack(archive,destination,expected,row):
 if core.sha(archive)!=expected:raise ValueError('Frozen carousel bundle checksum mismatch')
 with zipfile.ZipFile(archive) as z:
  names=z.namelist()
  if len(names)!=len(set(names)) or sum(i.file_size for i in z.infolist())>200_000_000:raise ValueError('Unexpected bundle inventory/size')
  for info in z.infolist():
   path=Path(info.filename)
   if path.is_absolute() or '..' in path.parts or ((info.external_attr>>16)&0o170000)==0o120000:raise ValueError('Unsafe bundle member')
  z.extractall(destination)
 review=core.read(destination/'Review.json')
 if set(names)!={'Review.json',*review['files']}:raise ValueError('Unexpected carousel files')
 for relative,digest in review['files'].items():
  if core.sha(destination/relative)!=digest:raise ValueError('Reviewed carousel input changed:'+relative)
 if review.get('kind')!='carousel_gallery' or any(review.get(k) is not True for k in ['source_review_passed','visual_qa_passed','fresh_independent_review_passed']):raise ValueError('Unready carousel review')
 if review.get('human_native_review_claimed') is not False:raise ValueError('Unexpected human review claim')
 if review['publish_at']!=row['publish_at'] or review['slug']!=row['slug']:raise ValueError('Bundle date/family differs from schedule')
 if not re.fullmatch(r'[0-9a-f]{64}',review.get('independent_review_sha256','')):raise ValueError('Independent review evidence missing')
 for key in ['independent_review_file','source_review_file','visual_qa_file','authorization_file']:
  if review.get(key) not in review['files']:raise ValueError('Unbound review evidence:'+key)
 if review['files'][review['independent_review_file']]!=review['independent_review_sha256']:raise ValueError('Independent review hash differs')
 authorization=core.read(destination/review['authorization_file'])
 if authorization!={'owner_instruction_date':'2026-10-27','format':'one_carousel_per_day','destination':'https://a-samadi.com','slug':row['slug'],'publish_at':row['publish_at'],'early_publication':False,'automatic_backfill':False}:raise ValueError('Carousel authorization differs')
 if len(review['media']['slides'])!=6 or len(set(review['media']['slides']))!=6:raise ValueError('Six distinct slide files required')
 for name in [*review['media']['slides'],review['media']['pdf'],'render_carousel_gallery.py','Website-Carousel-EN.json']:
  if name not in review['files']:raise ValueError('Unbound media/code/copy')
 copy=core.read(destination/'Website-Carousel-EN.json')
 if copy['slug']!=row['slug'] or copy['publish_at']!=row['publish_at']:raise ValueError('Copy differs from schedule')
 date.fromisoformat(copy['source_date']);date.fromisoformat(copy['source_checked_on'])
 if copy['source_date']>row['key'] or copy['source_checked_on']>row['key']:raise ValueError('Future source claim')
 return review

def obtain(config,row,temp,local=None):
 archive=temp/row['asset_name']
 if local:shutil.copyfile(local/row['asset_name'],archive)
 else:
  with archive.open('wb') as f:
   import subprocess
   subprocess.run(['gh','api','-H','Accept: application/octet-stream',f'repos/{config["repository"]}/releases/assets/{int(row["asset_id"])}'],stdout=f,check=True)
 folder=temp/archive.stem;folder.mkdir()
 return folder,unpack(archive,folder,row['sha256'],row)

def refuse_existing_day(site,due):
 for page in (site/'carousels').glob('*.html'):
  for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',page.read_text(),re.S):
   graph=json.loads(raw)
   for node in graph.get('@graph',[graph]):
    if node.get('@type')=='CollectionPage' and node.get('@id','').endswith('#gallery') and node.get('datePublished'):
     if datetime.fromisoformat(node['datePublished'].replace('Z','+00:00')).astimezone(core.ZONE).date()==due.astimezone(core.ZONE).date():raise ValueError('This day already has a published carousel')

def prepare(site,folder,review,stamp):
 before=core.inventory(site)
 spec=importlib.util.spec_from_file_location('reviewed_carousel_renderer',folder/'render_carousel_gallery.py');renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
 media={'slides':[str(folder/x) for x in review['media']['slides']],'pdf':str(folder/review['media']['pdf'])}
 renderer.render(site,folder,{'live_root':str(ROOT),'media':media},stamp)
 for name in ['enrich_metadata','build_author_boxes','build_analytics','build_topic_hubs','follow_blocks','build_feed','build_llms','build_ask_index','build_status_pages']:
  core.run(['python3','-B','scripts/'+name+'.py'],site)
 after=core.inventory(site);changed=sorted(k for k in after if before.get(k)!=after[k])
 if set(before)-set(after) or set(changed)-(set(review['public_allowlist']) | {'llms-full.txt'}):raise ValueError('Change outside reviewed gallery paths')
 return changed

def verify_live(config,commit,paths):
 core.verify_live(config,commit,paths)
 for relative in paths:
  if relative.endswith(('.pdf','.xml','.json','.txt')) and not relative.startswith('scripts/'):
   request=urllib.request.Request(config['site_url']+'/'+relative,headers={'User-Agent':'Ahmadreza-carousel-release-verifier/1.0'})
   with urllib.request.urlopen(request,timeout=90) as r:data=r.read()
   if data!=(ROOT/relative).read_bytes():raise RuntimeError('Live discovery/PDF mismatch:'+relative)

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--wait-for-slot',action='store_true');ap.add_argument('--local-bundles',type=Path);ap.add_argument('--owner-catchup-2026-10-28',action='store_true');args=ap.parse_args()
 config=core.read(CONFIG);validate(config);now=datetime.now(core.ZONE)
 catchup=core.read(CATCHUP) if args.owner_catchup_2026_10_28 else None
 if catchup and (args.verify or args.wait_for_slot or args.local_bundles):raise ValueError('Catch-up must use exact remote bundle alone')
 selected=lambda instant:owner_catchup_rows(config,instant,catchup) if catchup else rows_now(config,instant)
 rows=selected(now) if catchup else config['carousels'] if args.verify else rows_now(config,now,args.wait_for_slot)
 if not rows:
  missed=[r['key'] for r in config['carousels'] if now>datetime.fromisoformat(r['publish_at'])+timedelta(minutes=30) and not (ROOT/'data/carousel-publications'/f'{r["key"]}.json').exists()]
  if missed:print('::warning::MISSED carousel website slot(s):'+','.join(missed)+'; no automatic backfill. Other due film work may continue.')
  print('No carousel due; no public change.');return
 if core.run(['git','status','--porcelain=v1','--untracked-files=no'],ROOT):raise ValueError('Concurrent tracked changes')
 base=core.run(['git','rev-parse','HEAD'],ROOT);original=core.inventory(ROOT);warming=not args.verify and not catchup and not rows_now(config,now)
 with tempfile.TemporaryDirectory(prefix='reviewed-carousel-') as td:
  temp=Path(td).resolve();site=temp/'site';shutil.copytree(ROOT,site,ignore=shutil.ignore_patterns('__pycache__','node_modules','.DS_Store'));changed=set();last=None
  for row in rows:
   folder,review=obtain(config,row,temp,args.local_bundles);existing=ROOT/'carousels'/f'{row["slug"]}.html';receipt_path=Path('data/carousel-publications')/f'{row["key"]}.json'
   if existing.exists():
    receipt=core.read(ROOT/receipt_path)
    if receipt['bundle_sha256']!=row['sha256'] or receipt['slug']!=row['slug'] or receipt['scheduled_at']!=row['publish_at']:raise ValueError('Existing gallery receipt differs')
    for name in [*review['media']['slides'],review['media']['pdf']]:
     target=ROOT/'assets/carousels'/row['slug']/('carousel.pdf' if name==review['media']['pdf'] else f'slide-{review["media"]["slides"].index(name)+1:02d}.png')
     if core.sha(target)!=review['files'][name]:raise ValueError('Existing gallery media differs')
    if args.verify:continue
    verify_live(config,base,receipt['public_paths']);print('Already published; no duplicate commit.');return
   if not args.verify:refuse_existing_day(ROOT,datetime.fromisoformat(row['publish_at']))
   changed.update(prepare(site,folder,review,now.isoformat(timespec='seconds')));last=review
  count=core.checks(site)
  if args.verify:
   if core.inventory(ROOT)!=original:raise ValueError('Private rehearsal changed active checkout')
   print(f'PASS:{len(rows)}carousel bundles,{count}currentchecks;privateonly');return
  if warming:
   due=datetime.fromisoformat(rows[0]['publish_at']);deadline=time.monotonic()+10800
   while datetime.now(core.ZONE)<due:
    seconds=(due-datetime.now(core.ZONE)).total_seconds()
    if time.monotonic()+seconds>deadline+1:raise ValueError('Bounded prewarm expired')
    print(f'PRIVATE_CAROUSEL_READY {rows[0]["key"]};waiting {seconds:.0f}s;no public files changed',flush=True);time.sleep(min(seconds,60))
   stamp=datetime.now(core.ZONE).isoformat(timespec='seconds');core.retime_private_stage(site,changed,now.isoformat(timespec='seconds'),stamp);count=core.checks(site)
  else:stamp=now.isoformat(timespec='seconds')
  if len(rows)!=1 or selected(datetime.now(core.ZONE))!=rows:raise ValueError('Early/expired release window')
  core.run(['git','fetch','origin','main'],ROOT)
  if core.run(['git','rev-parse','origin/main'],ROOT)!=base or core.inventory(ROOT)!=original:raise ValueError('Concurrent main/checkout change')
  for relative in sorted(changed):
   dest=ROOT/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(site/relative,dest)
  receipt_path='data/carousel-publications/'+rows[0]['key']+'.json'
  core.write(ROOT/receipt_path,{'scheduled_at':rows[0]['publish_at'],'prepared_at':now.isoformat(timespec='seconds'),'release_started_at':datetime.now(core.ZONE).isoformat(timespec='seconds'),'content_timestamp':stamp,'private_preflight_before_slot':warming,'automatic_daily_exception':not bool(catchup),'owner_authorized_catchup':catchup,'format':'carousel_gallery','human_native_review_claimed':False,'slug':last['slug'],'bundle_sha256':rows[0]['sha256'],'site_checks_passed':count,'public_paths':sorted(changed)})
  changed.add(receipt_path);core.run(['git','add','--',*sorted(changed)],ROOT);core.run(['git','diff','--cached','--check'],ROOT)
  if set(core.run(['git','diff','--cached','--name-only'],ROOT).splitlines())!=changed:raise ValueError('Unexpected staged files')
  if selected(datetime.now(core.ZONE))!=rows:raise ValueError('Window expired before commit')
  core.run(['git','config','user.name','github-actions[bot]'],ROOT);core.run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],ROOT)
  core.run(['git','commit','-m','Publish reviewed carousel '+rows[0]['key']],ROOT);core.run(['git','push','origin','HEAD:main'],ROOT);commit=core.run(['git','rev-parse','HEAD'],ROOT);verify_live(config,commit,sorted(changed));print('Published due carousel once:'+last['slug'])
if __name__=='__main__':main()
