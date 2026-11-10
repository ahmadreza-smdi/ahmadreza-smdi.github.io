import {encodeState,decodeState} from './share-state.mjs?v=20261015-share1';
export function initializeSharing(page,form){
 const kind=page.dataset.page;
 const controls=[...form.elements].filter(e=>e.name);
 const fields=controls.map(e=>({name:e.name,type:e.type==='number'?'number':e.type==='checkbox'?'checkbox':'choice',...(e.type==='number'&&e.max!==''?{max:Number(e.max)}:{}),options:e.options?[...e.options].map(o=>o.value):[]}));
 const status=page.querySelector('[data-share-status]'),link=page.querySelector('[data-share-link]'),linkLabel=page.querySelector('[data-share-link-label]');
 const renderPrint=()=>{
  const summary=page.querySelector('[data-print-inputs]');summary.replaceChildren();
  const title=document.createElement('h2');title.textContent='Inputs used';summary.append(title);
  const origin=document.createElement('p');const example=form.querySelector('[data-example-note]');origin.textContent=example&&!example.hidden?example.textContent:'User-entered inputs; not independently verified quotes or facts.';summary.append(origin);
  const list=document.createElement('dl');list.className='print-input-list';
  for(const e of controls){if(e.disabled)continue;const label=form.querySelector(`label[for="${e.id}"]`)||e.closest('label');const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label?.textContent.trim()||e.name;dd.textContent=e.type==='checkbox'?(e.checked?'Confirmed in this browser':'Not confirmed'):e.tagName==='SELECT'?(e.value?e.selectedOptions[0].textContent:'Unknown'):e.value.trim()||'Unknown';row.append(dt,dd);list.append(row);}
  summary.append(list);
 };
 page.addEventListener('calculator:render',renderPrint);
 page.querySelector('[data-share]').addEventListener('click',()=>{
  try{const inputs=Object.create(null);for(const e of controls){if(e.disabled)continue;inputs[e.name]=e.type==='number'?(e.value.trim()===''?null:Number(e.value)):e.type==='checkbox'?false:e.value||null;}
   const route=kind==='rental'?'rental-cash-flow':'dubai-purchase-cost';const url=new URL(`/tools/embed/${route}.html`,location.href);const example=form.querySelector('[data-example-note]');url.hash=encodeState(kind,inputs,fields,example&&!example.hidden?'fictional-example':'user-inputs');
   link.value=url.href;linkLabel.hidden=false;link.hidden=false;link.select();status.textContent='Link ready to copy. Anyone with it can read these inputs. Quote-review confirmations are not carried over.';
  }catch(e){status.textContent=e.message;link.hidden=true;linkLabel.hidden=true;}
 });
 page.querySelector('[data-print]').addEventListener('click',()=>window.print());
 form.querySelector('[data-clear]').addEventListener('click',()=>{link.value='';link.hidden=true;linkLabel.hidden=true;status.textContent='';if(location.hash.startsWith('#calc='))history.replaceState(null,'',location.pathname+location.search);});
 page.addEventListener('calculator:render',()=>{if(status.textContent.startsWith('Link ready to copy.')){link.value='';link.hidden=true;linkLabel.hidden=true;status.textContent='Inputs changed. Create a new result link to share the current calculation.';}});
 function restore(){
  try{const saved=decodeState(location.hash,kind,fields);if(saved){link.value='';link.hidden=true;linkLabel.hidden=true;for(const e of controls){const v=saved[e.name];if(e.type==='checkbox')e.checked=false;else e.value=v===null?'':String(v);}form.querySelector('[data-example-note]').hidden=saved.origin!=='fictional-example';status.textContent=kind==='purchase'?'Saved inputs restored. Check the dated fee basis and your quotes yourself; no review confirmation was restored.':'Saved inputs restored. Confirm the property figures and annual period before using this calculation.';}}
  catch(e){status.textContent=e.message+' This link was not applied; existing inputs are unchanged.';}
 }
 window.addEventListener('hashchange',()=>{restore();page.dispatchEvent(new Event('calculator:restore'));});
 restore();
 renderPrint();
}
