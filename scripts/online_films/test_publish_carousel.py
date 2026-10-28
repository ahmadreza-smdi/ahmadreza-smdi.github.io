import copy,hashlib,importlib.util,json,sys,tempfile,unittest,zipfile
from datetime import datetime,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import publish_carousel as p

def config():
 return {'schema':1,'timezone':'Asia/Tehran','daily_count':1,'local_slot':'10:00','carousels':[{'key':'2026-10-28','slug':'tech-trend-permissions','publish_at':'2026-10-28T10:00:00+03:30','sha256':'a'*64,'asset_name':'reviewed-carousel.zip','asset_id':42}]}
def artifact(folder,change=None,extra=None):
 files={f's{i}.png':f'slide{i}'.encode() for i in range(6)}
 copydata={'slug':'tech-trend-permissions','publish_at':'2026-10-28T10:00:00+03:30','source_date':'2026-10-26','source_checked_on':'2026-10-27'}
 files['Authorization.json']=json.dumps({'owner_instruction_date':'2026-10-27','format':'one_carousel_per_day','destination':'https://a-samadi.com','slug':copydata['slug'],'publish_at':copydata['publish_at'],'early_publication':False,'automatic_backfill':False}).encode()
 files.update({'Independent-Review.json':b'fixture independent review','Source-QA.json':b'fixture primary review','Visual-QA.json':b'fixture visual review','doc.pdf':b'fixture pdf','render_carousel_gallery.py':b'# fixture only','Website-Carousel-EN.json':json.dumps(copydata).encode()})
 review={'kind':'carousel_gallery','source_review_passed':True,'visual_qa_passed':True,'fresh_independent_review_passed':True,'human_native_review_claimed':False,'independent_review_sha256':hashlib.sha256(files['Independent-Review.json']).hexdigest(),'independent_review_file':'Independent-Review.json','source_review_file':'Source-QA.json','visual_qa_file':'Visual-QA.json','authorization_file':'Authorization.json','publish_at':copydata['publish_at'],'slug':copydata['slug'],'files':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()},'media':{'slides':[f's{i}.png' for i in range(6)],'pdf':'doc.pdf'},'public_allowlist':[]}
 if change:change(review,files)
 zpath=folder/'bundle.zip'
 with zipfile.ZipFile(zpath,'w') as z:
  z.writestr('Review.json',json.dumps(review))
  for k,v in files.items():z.writestr(k,v)
  if extra:z.writestr(*extra)
 return zpath,p.core.sha(zpath)

class Guards(unittest.TestCase):
 def catchup(self):
  c=config();r=c['carousels'][0]
  return c,{'owner_instruction_date':'2026-10-28','key':r['key'],'slug':r['slug'],'bundle_sha256':r['sha256'],'destination':'https://a-samadi.com','action':'publish_missed_carousel_once','not_before':'2026-10-28T10:30:01+03:30','expires_at':'2026-10-28T23:30:00+03:30'}
 def test_owner_catchup_exact_same_day_and_window_only(self):
  c,a=self.catchup()
  for stamp in ['2026-10-28T10:30:01+03:30','2026-10-28T17:00:00+03:30','2026-10-28T23:30:00+03:30']:
   self.assertEqual(c['carousels'],p.owner_catchup_rows(c,datetime.fromisoformat(stamp),a))
  for stamp in ['2026-10-28T10:30:00+03:30','2026-10-28T23:30:01+03:30','2026-10-29T17:00:00+03:30']:
   with self.assertRaises(ValueError):p.owner_catchup_rows(c,datetime.fromisoformat(stamp),a)
 def test_owner_catchup_refuses_changed_authority_hash_or_row(self):
  c,a=self.catchup();now=datetime.fromisoformat('2026-10-28T17:00:00+03:30')
  for field in a:
   changed=dict(a);changed[field]='changed'
   with self.assertRaises(ValueError):p.owner_catchup_rows(c,now,changed)
  changed=copy.deepcopy(c);changed['carousels'][0]['sha256']='b'*64
  with self.assertRaises(ValueError):p.owner_catchup_rows(changed,now,a)
  changed=copy.deepcopy(c);changed['carousels'][0]['key']='2026-10-29'
  with self.assertRaises(ValueError):p.owner_catchup_rows(changed,now,a)
  changed=copy.deepcopy(c);changed['carousels'].append(copy.deepcopy(changed['carousels'][0]))
  with self.assertRaises(ValueError):p.owner_catchup_rows(changed,now,a)
 def test_cadence_and_timezone(self):
  p.validate(config())
  for key,value in [('daily_count',2),('local_slot','21:00'),('timezone','UTC')]:
   d=config();d[key]=value
   with self.assertRaises(ValueError):p.validate(d)
 def test_one_carousel_per_day(self):
  c=config();c['carousels'].append(copy.deepcopy(c['carousels'][0]))
  with self.assertRaises(ValueError):p.validate(c)
 def test_schedule_row_slot(self):
  for date in ['2026-10-28T10:00:00+00:00','2026-10-28T10:01:00+03:30','2026-10-29T10:00:00+03:30']:
   c=config();c['carousels'][0]['publish_at']=date
   with self.assertRaises(ValueError):p.validate(c)
 def test_slug_and_asset_path(self):
  for k,v in [('slug','../../bad'),('asset_name','../bad.zip'),('sha256','z'*64)]:
   c=config();c['carousels'][0][k]=v
   with self.assertRaises(ValueError):p.validate(c)
 def test_preparation_is_today_and_bounded(self):
  c=config();dt=lambda t:datetime.fromisoformat(t)
  self.assertEqual(p.rows_now(c,dt('2026-10-27T21:00:00+03:30'),True),[])
  self.assertEqual(p.rows_now(c,dt('2026-10-28T06:59:59+03:30'),True),[])
  self.assertEqual(len(p.rows_now(c,dt('2026-10-28T07:00:00+03:30'),True)),1)
 def test_no_early_or_late_release(self):
  c=config();dt=lambda t:datetime.fromisoformat(t)
  self.assertEqual(p.rows_now(c,dt('2026-10-28T09:59:59+03:30')),[])
  self.assertEqual(len(p.rows_now(c,dt('2026-10-28T10:00:00+03:30'))),1)
  self.assertEqual(len(p.rows_now(c,dt('2026-10-28T10:30:00+03:30'))),1)
  self.assertEqual(p.rows_now(c,dt('2026-10-28T10:30:01+03:30')),[])
  self.assertEqual(p.rows_now(c,dt('2026-10-29T10:00:00+03:30'),True),[])
 def check_bundle(self,change=None,extra=None,expected=None):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);z,digest=artifact(folder,change,extra);out=folder/'out';out.mkdir()
   return p.unpack(z,out,expected or digest,config()['carousels'][0])
 def test_valid_frozen_bundle(self):self.assertEqual(self.check_bundle()['kind'],'carousel_gallery')
 def test_checksum_rejection(self):
  with self.assertRaises(ValueError):self.check_bundle(expected='0'*64)
 def test_each_review_gate_required(self):
  for field in ['source_review_passed','visual_qa_passed','fresh_independent_review_passed']:
   with self.assertRaises(ValueError):self.check_bundle(lambda r,f:r.update({field:False}))
 def test_review_evidence_must_be_bound(self):
  with self.assertRaises(ValueError):self.check_bundle(lambda r,f:r.update(independent_review_file='missing.json'))
  with self.assertRaises(ValueError):self.check_bundle(lambda r,f:r.update(independent_review_sha256='b'*64))
 def test_no_false_human_claim(self):
  with self.assertRaises(ValueError):self.check_bundle(lambda r,f:r.update(human_native_review_claimed=True))
 def test_wrong_kind_or_date(self):
  for k,v in [('kind','film'),('publish_at','2026-10-29T10:00:00+03:30'),('independent_review_sha256','unknown')]:
   with self.assertRaises(ValueError):self.check_bundle(lambda r,f:r.update({k:v}))
 def test_media_hash_or_binding_changed(self):
  with self.assertRaises(ValueError):self.check_bundle(lambda r,f:f.update({'s0.png':b'changed'}))
  with self.assertRaises(ValueError):self.check_bundle(lambda r,f:r['media']['slides'].__setitem__(0,'unbound.png'))
 def test_traversal_and_unexpected_member(self):
  for name in ['../escape','/absolute','unexpected.txt']:
   with self.assertRaises(ValueError):self.check_bundle(extra=(name,b'bad'))
 def test_authorization_is_bound_and_exact(self):
  with self.assertRaises(ValueError):self.check_bundle(lambda r,f:r.update(authorization_file='missing.json'))
  def replace_auth(r,f):
   a=json.loads(f['Authorization.json']);a['early_publication']=True;f['Authorization.json']=json.dumps(a).encode();r['files']['Authorization.json']=hashlib.sha256(f['Authorization.json']).hexdigest()
  with self.assertRaises(ValueError):self.check_bundle(replace_auth)
 def test_gallery_day_guard_does_not_consume_film_slot(self):
  with tempfile.TemporaryDirectory() as td:
   site=Path(td);(site/'carousels').mkdir();due=datetime.fromisoformat('2026-10-28T10:00:00+03:30')
   p.refuse_existing_day(site,due)
   node={'@type':'CollectionPage','@id':'https://a-samadi.com/carousels/test.html#gallery','datePublished':due.isoformat()}
   (site/'carousels/test.html').write_text('<script type="application/ld+json">'+json.dumps(node)+'</script>')
   with self.assertRaises(ValueError):p.refuse_existing_day(site,due)
   p.refuse_existing_day(site,due+timedelta(days=1))
if __name__=='__main__':unittest.main()
