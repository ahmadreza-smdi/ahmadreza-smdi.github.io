import {summarize} from './study-model.mjs?v=20261021-range1';
const $=id=>document.getElementById(id),money=x=>x===null?'Undefined':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(x);
const data=JSON.parse($('study-data').textContent);
const keys=data.fields.map(f=>f.key),percent=new Set(data.fields.filter(f=>f.percent).map(f=>f.key));
let current=data.scenarios[0],page=0,selected=data.metros[0],results=[];
const el=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
function setCase(s){current=s;for(const k of keys)$(k).value=s[k]*(percent.has(k)?100:1);}
function inputs(){const s={id:current.id};for(const k of keys){if($(k).value.trim()==='')throw Error('Complete every assumption; use zero only when intentionally assumed.');s[k]=Number($(k).value)/(percent.has(k)?100:1);}return s;}
function chart(lo,hi,extent){
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 300 30');svg.setAttribute('role','img');svg.setAttribute('aria-label',`Annual cash-budget range ${money(lo)} to ${money(hi)}`);
 const x=v=>150+v/extent*140;
 for(const [a,b,cls] of [[150,150,'zero'],[x(lo),x(hi),'range']]){const l=document.createElementNS(ns,'line');l.setAttribute('x1',a);l.setAttribute('x2',b);l.setAttribute('y1',cls==='zero'?3:15);l.setAttribute('y2',cls==='zero'?27:15);l.setAttribute('class',cls);svg.append(l);}
 for(const v of [lo,hi]){const c=document.createElementNS(ns,'circle');c.setAttribute('cx',x(v));c.setAttribute('cy',15);c.setAttribute('r',4);svg.append(c);}return svg;
}
function details(s){
 $('selected-name').textContent=selected.name;$('selected-proxy').textContent=`ACS 2024 owner-stock value proxy ${money(selected.price)}; margin of error ${money(selected.moe)}. ${selected.exception?'HUD statutory partial-county exception: Sullivan City/Crawford County.':'County sets agree; town/subcounty and housing-population equivalence are not established.'}`;
 const body=$('area-body');body.replaceChildren();
 try{const r=summarize(selected,s);$('threshold').textContent=`Break-even gross monthly rent under these assumptions: ${money(r.threshold)}. Price-proxy endpoint surplus range: ${money(r.priceMin)} to ${money(r.priceMax)} annually; not a confidence interval.`;
 for(const a of r.details){const tr=el('tr');for(const text of [a.name,a.code,money(a.rent),money(a.result.annual_cash_surplus)])tr.append(el('td',text));body.append(tr);}
 const d=r.details[0].result;$('budget').textContent=`At the first listed HUD area's rent: receipts ${money(d.annual_receipts)} − management ${money(d.annual_management)} − fixed budget ${money(d.annual_fixed_budget)} − principal/interest ${money(d.annual_principal_interest)} = annual surplus ${money(d.annual_cash_surplus)}. Fixed budget includes tax, insurance, maintenance reserve, HOA, other costs and mortgage insurance once.`;
 }catch(e){$('threshold').textContent=e.message;$('budget').textContent='This metro cannot be calculated with the selected assumptions; it is not assigned a zero result.';}
}
function invalidateShare(){
 const link=$('share-url');link.value='';link.hidden=true;$('share-status').textContent='';
}
function render(preserveShareNotice=false){
 if(!preserveShareNotice)invalidateShare();
 let s;try{s=inputs();$('error').textContent='';$('download-current').disabled=false;}catch(e){$('error').textContent=e.message;results=[];$('result-body').replaceChildren();$('area-body').replaceChildren();$('print-assumptions').replaceChildren();$('count').textContent='Results cleared until every assumption is complete.';$('threshold').textContent='No current calculation.';$('budget').textContent='';$('download-current').disabled=true;return;}
 $('print-assumptions').replaceChildren();for(const f of data.fields){const item=el('div');item.append(el('dt',f.label),el('dd',String(s[f.key]*(f.percent?100:1))));$('print-assumptions').append(item);}
 const query=$('search').value.trim().toLowerCase();results=data.metros.filter(m=>m.name.toLowerCase().includes(query)||m.cbsa.includes(query)).map(m=>{try{return {m,...summarize(m,s)};}catch(e){return {m,error:e.message};}});
 if($('sort').value==='surplus')results.sort((a,b)=>(a.min??-Infinity)-(b.min??-Infinity));
 const pages=Math.max(1,Math.ceil(results.length/20));page=Math.min(page,pages-1);
 const valid=results.filter(r=>!r.error),extent=Math.max(1,...valid.flatMap(r=>[Math.abs(r.min),Math.abs(r.max)]));
 $('count').textContent=`${results.length} metros shown; ${valid.length} calculated; ${results.length-valid.length} unresolved with these inputs. Ranges describe scenarios, not market rankings.`;
 const body=$('result-body');body.replaceChildren();
 results.forEach((r,i)=>{const tr=el('tr');tr.className='result-row';tr.hidden=i<page*20||i>=(page+1)*20;const td=el('td'),button=el('button',r.m.name);button.className='metro-button';button.addEventListener('click',()=>{invalidateShare();selected=r.m;details(s);$('detail').scrollIntoView({behavior:'auto',block:'start'});});td.append(button);tr.append(td,el('td',r.m.areas.length));
 const graphic=el('td');if(!r.error)graphic.append(chart(r.min,r.max,extent));tr.append(graphic,el('td',r.error||`${money(r.min)} to ${money(r.max)}`));body.append(tr);});
 $('page').textContent=`Page ${page+1} of ${pages}`;$('previous').disabled=page===0;$('next').disabled=page>=pages-1;
 $('axis').textContent=`Chart scale: ${money(-extent)} to ${money(extent)} annually; centre line is zero.`;details(s);
}
for(const f of data.fields){const label=el('label',f.label),input=el('input');input.id=f.key;input.type='number';input.min='0';input.step=f.step||'any';if(f.max!==undefined)input.max=f.max;label.append(input);$('assumptions').append(label);input.addEventListener('input',()=>{page=0;render();});}
data.scenarios.forEach(s=>{const o=el('option',s.label);o.value=s.id;$('preset').append(o);});
$('preset').addEventListener('change',()=>{setCase(data.scenarios.find(s=>s.id===$('preset').value));page=0;render();});
for(const id of ['search','sort'])$(id).addEventListener('input',()=>{page=0;render();});
$('previous').addEventListener('click',()=>{page--;render();});$('next').addEventListener('click',()=>{page++;render();});
function csvCell(x){return '"'+String(x??'').replaceAll('"','""')+'"';}
$('download-current').addEventListener('click',()=>{let s;try{s=inputs();}catch(e){$('error').textContent=e.message;return;}const fields=['cbsa','metro','hud_fiscal_year','acs_year','owner_value_proxy_usd','owner_value_moe_usd','hud_areas','cash_surplus_min_usd','cash_surplus_max_usd','price_endpoint_min_usd','price_endpoint_max_usd','status',...keys];const rows=results.map(r=>[r.m.cbsa,r.m.name,2027,2024,r.m.price,r.m.moe,r.m.areas.map(a=>a.code).join(';'),r.min,r.max,r.priceMin,r.priceMax,r.error||'illustrative cash budget; not investment return',...keys.map(k=>s[k])]);const blob=new Blob([[fields,...rows].map(row=>row.map(csvCell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});const a=el('a');a.href=URL.createObjectURL(blob);a.download='rent-own-current-scenario.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);});
$('print').addEventListener('click',()=>window.print());
function restoreLink(){
 if(!location.hash.startsWith('#scenario='))return;
 try{const saved=JSON.parse(decodeURIComponent(location.hash.slice(10)));
 if(saved.version!==1 || !saved.inputs || !keys.every(k=>Number.isFinite(saved.inputs[k])))throw Error('Unsupported scenario link.');
 const target=data.metros.find(m=>m.cbsa===saved.cbsa);if(!target)throw Error('Unknown metro in scenario link.');
 const s={...current,...saved.inputs};summarize(target,s);setCase(s);
 if(typeof saved.search==='string')$('search').value=saved.search.slice(0,150);
 if(typeof saved.cbsa==='string')selected=data.metros.find(m=>m.cbsa===saved.cbsa)||selected;
 }catch(e){$('share-status').textContent='This scenario link could not be restored; the initial case is shown.';}
}
$('share').addEventListener('click',()=>{try{const s=inputs();summarize(selected,s);const state={version:1,inputs:Object.fromEntries(keys.map(k=>[k,s[k]])),search:$('search').value,cbsa:selected.cbsa};$('share-url').value=location.href.split('#')[0]+'#scenario='+encodeURIComponent(JSON.stringify(state));$('share-url').hidden=false;$('share-url').select();$('share-status').textContent='Scenario link ready to copy. Assumptions are in the link fragment; they are not sent to the website server.';}catch(e){$('share-status').textContent=e.message;}});
setCase(current);restoreLink();render(true);
