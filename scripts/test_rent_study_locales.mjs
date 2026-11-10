/** Execute both actual UI modules against the same data and a minimal DOM.
 * This tests computations/rendered values and localized states, not browser layout.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const {summarize}=await import(pathToFileURL(path.join(root,'studies/rent-own-2026/study-model.mjs')));
const source=fs.readFileSync(path.join(root,'studies/rent-own-2026/index.html'),'utf8');
const embedded=(html,id)=>JSON.parse(html.match(new RegExp('<script[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'))[1]);
const data=embedded(source,'study-data');
assert.equal(data.metros.length,393);
function harness(lang,hash=''){
 const html=lang==='en'?source:fs.readFileSync(path.join(root,lang,'studies/rent-own-2026/index.html'),'utf8');
 assert.deepEqual(embedded(html,'study-data'),data);
 const nodes=new Map();let capturedBlob;
 class E{
  constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.listeners={};this._text='';this._value='';}
  set id(v){this._id=v;nodes.set(v,this);}get id(){return this._id;}
  set value(v){this._value=String(v);}get value(){return this._value;}
  set textContent(v){this._text=String(v);this.children=[];}get textContent(){return this._text+this.children.map(c=>c.textContent??String(c)).join('');}
  append(...xs){this.children.push(...xs);}replaceChildren(...xs){this._text='';this.children=xs;}
  setAttribute(k,v){this.attributes[k]=String(v);}addEventListener(k,f){this.listeners[k]=f;}
  scrollIntoView(){}select(){}click(){this.listeners.click?.();}
 }
 for(const [,id] of html.matchAll(/\bid="([^"]+)"/g)){const e=new E('div');e.id=id;}
 nodes.get('study-data').textContent=JSON.stringify(data);nodes.get('search').value='';nodes.get('sort').value='name';
 const locale=lang==='en'?null:embedded(html,'study-locale');if(locale)nodes.get('study-locale').textContent=JSON.stringify(locale);
 const filename=lang==='en'?'study-ui.mjs':'study-ui-localized.mjs';
 const code=fs.readFileSync(path.join(root,'studies/rent-own-2026',filename),'utf8').replace(/^import .*?;\n/m,'');
 const ctx={summarize,document:{getElementById:id=>nodes.get(id),createElement:t=>new E(t),createElementNS:(_,t)=>new E(t)},Intl,console,location:{hash,href:'https://a-samadi.com/'+(lang==='en'?'':lang+'/')+'studies/rent-own-2026/'},window:{print(){}},Blob,URL:{createObjectURL:b=>{capturedBlob=b;return 'blob:test';},revokeObjectURL(){}},setTimeout:f=>f()};
 vm.runInNewContext(code,ctx,{filename});
 const event=(id,type)=>nodes.get(id).listeners[type]();
 const geometry=()=>nodes.get('result-body').children.map(row=>({name:row.children[0].textContent,areas:row.children[1].textContent,graphic:row.children[2].children.map(svg=>svg.children.map(x=>x.attributes))}));
 return {nodes,locale,event,geometry,blob:()=>capturedBlob};
}
const en=harness('en');const report=[];
for(const lang of ['fa','ar']){
 const h=harness(lang);let states=0;
 for(const preset of data.scenarios){
  for(const ui of [en,h]){ui.nodes.get('preset').value=preset.id;ui.event('preset','change');}
  assert.deepEqual(h.geometry(),en.geometry());
  assert.equal(h.nodes.get('result-body').children.length,393);
  for(const f of data.fields){assert.equal(h.nodes.get(f.key).value,en.nodes.get(f.key).value);}
  assert.equal(h.nodes.get('preset').children.find(x=>x.value===preset.id).textContent,h.locale.scenarios[preset.id]);
  const expected=summarize(data.metros[0],preset);
  const fmt=x=>new Intl.NumberFormat(h.locale.locale,{style:'currency',currency:'USD',maximumFractionDigits:0}).format(x);
  assert.ok(h.nodes.get('budget').textContent.includes(fmt(expected.details[0].result.annual_cash_surplus)));
  assert.ok(h.nodes.get('threshold').textContent.includes(fmt(expected.threshold)));
  h.nodes.get('download-current').click();en.nodes.get('download-current').click();
  assert.equal(await h.blob().text(),await en.blob().text());
  states++;
 }
 h.nodes.get('occupied_months').value='0';h.event('occupied_months','input');
 assert.ok(h.nodes.get('threshold').textContent.includes(h.locale.messages.undefined));states++;
 h.nodes.get('share').click();assert.equal(h.nodes.get('share-status').textContent,h.locale.messages.share);states++;
 h.nodes.get('occupied_months').value='';h.event('occupied_months','input');
 assert.equal(h.nodes.get('error').textContent,h.locale.messages.required);assert.equal(h.nodes.get('result-body').children.length,0);assert.equal(h.nodes.get('download-current').disabled,true);states++;
 h.nodes.get('occupied_months').value='11';h.nodes.get('monthly_utilities').value='999999';h.event('monthly_utilities','input');
 assert.equal(h.nodes.get('threshold').textContent,h.locale.messages.utilities);assert.ok(h.nodes.get('result-body').children.every(r=>r.children[3].textContent===h.locale.messages.utilities));states++;
 for(const f of data.fields){assert.ok(h.nodes.get('assumptions').children.some(x=>x.textContent===h.locale.fields[f.key]));}
 assert.equal(h.nodes.get('preset').children.length,3);
 report.push({language:lang,tested_states:states,metros_per_scenario:393,scenario_geometry_matches_original:true,valid_scenario_csv_bytes_match_original:true,localized_fields:12,localized_presets:3,missing_and_zero_distinct:true,localized_errors_and_share:true});
}

// Regression: shared scenarios must represent current inputs and known metros.
for(const lang of ['en','fa','ar']){
 const h=harness(lang);h.nodes.get('share').click();
 assert.equal(h.nodes.get('share-url').hidden,false);
 const saved=JSON.parse(decodeURIComponent(h.nodes.get('share-url').value.split('#scenario=')[1]));
 h.nodes.get('search').value='Boston';h.event('search','input');
 assert.equal(h.nodes.get('share-url').hidden,true);assert.equal(h.nodes.get('share-url').value,'');
 h.nodes.get('search').value='';h.event('search','input');h.nodes.get('share').click();
 h.nodes.get('result-body').children[1].children[0].children[0].click();
 assert.equal(h.nodes.get('share-url').hidden,true);
 const bad=harness(lang,'#scenario='+encodeURIComponent(JSON.stringify({...saved,cbsa:'00000',inputs:{...saved.inputs,occupied_months:3}})));
 assert.equal(bad.nodes.get('occupied_months').value,String(data.scenarios[0].occupied_months));
 assert.ok(bad.nodes.get('share-status').textContent.length>0);
 const good=harness(lang,'#scenario='+encodeURIComponent(JSON.stringify({...saved,cbsa:data.metros[1].cbsa,inputs:{...saved.inputs,occupied_months:3}})));
 assert.equal(good.nodes.get('occupied_months').value,'3');assert.equal(good.nodes.get('selected-name').textContent,data.metros[1].name);
 h.nodes.get('property_tax_fraction').value='1e308';h.event('property_tax_fraction','input');
 const expected=lang==='en'?'Cash-budget calculation exceeds numeric range; revise inputs':h.locale.errors['Cash-budget calculation exceeds numeric range; revise inputs'];
 assert.equal(h.nodes.get('threshold').textContent,expected);
 assert.ok(h.nodes.get('result-body').children.every(r=>r.children[3].textContent===expected));
 assert.ok(!h.nodes.get('axis').textContent.includes('NaN'));
 report.push({language:lang,share_invalidated_on_input_and_metro:true,unknown_metro_rejected:true,known_metro_restored:true,overflow_localized_and_cleared:true});
}
console.log(JSON.stringify({status:'PASS',checks:report},null,2));
