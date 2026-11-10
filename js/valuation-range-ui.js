(function () {
 'use strict';
 const form=document.querySelector('#range-form');if(!form)return;
 const rows=[...form.querySelectorAll('[data-estimate]')],result=document.querySelector('#range-results'),error=document.querySelector('#range-error');
 const share=document.querySelector('#share-link'),message=document.querySelector('#share-message');
 const currency=document.querySelector('#currency');
 const n=v=>new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(v);
 function values(){return rows.filter(r=>r.value!=='').map(r=>Number(r.value));}
 function clear(){result.hidden=true;share.value='';message.textContent='';error.textContent='';}
 function calculate(){
  clear();if(!form.reportValidity())return false;
  try{
   const vals=values(),s=ValuationRange.summarize(vals);
   for(const key of ['low','high','median'])document.querySelector('[data-result="'+key+'"]').textContent=currency.value+' '+n(s[key]);
   document.querySelector('[data-result="spread"]').textContent=n(s.spread)+'%';
   document.querySelector('#next-check').textContent=s.next;
   const body=document.querySelector('#estimate-rows');body.replaceChildren();
   let index=0;
   rows.forEach((r,i)=>{if(r.value==='')return;const tr=document.createElement('tr');const label=document.querySelector('#label-'+i).value.trim()||'Estimate '+(i+1);
    [label,currency.value+' '+n(vals[index]),n(s.deviations[index])+'%',s.flagged[index]?'Review: more than 10% from median':'Within 10% of median'].forEach(t=>{const td=document.createElement('td');td.textContent=t;tr.append(td);});body.append(tr);index++;});
   result.hidden=false;return true;
  }catch(e){error.textContent=e.message;return false;}
 }
 form.addEventListener('submit',e=>{e.preventDefault();calculate();});form.addEventListener('input',clear);
 document.querySelector('#use-example').addEventListener('click',()=>{rows.forEach((r,i)=>r.value=i<3?[950000,1000000,1050000][i]:'');rows.forEach((r,i)=>document.querySelector('#label-'+i).value=i<3?['Fictional AI estimate','Fictional broker opinion','Fictional appraisal'][i]:'');currency.value='AED';calculate();message.textContent='Fictional teaching example loaded; these are not property evidence.';});
 document.querySelector('#clear-estimates').addEventListener('click',()=>{form.reset();clear();});
 document.querySelector('#make-share').addEventListener('click',()=>{if(!calculate())return;const data={version:1,currency:currency.value,estimates:rows.map((r,i)=>({value:r.value,label:document.querySelector('#label-'+i).value}))};
  share.value='https://a-samadi.com/tools/valuation-range.html#scenario='+encodeURIComponent(JSON.stringify(data));share.focus();share.select();message.textContent='Link selected. Copy it to share only if you intend to disclose these amounts and source labels. It includes your inputs, not independent verification.';});
 document.querySelector('#print-range').addEventListener('click',()=>{if(calculate())window.print();});
 if(location.hash.startsWith('#scenario=')){
  try{const data=JSON.parse(decodeURIComponent(location.hash.slice(10)));if(data.version!==1||!['AED','USD','EUR','GBP','Other units'].includes(data.currency)||!Array.isArray(data.estimates)||data.estimates.length!==5)throw Error();
   const supplied=data.estimates.filter(x=>x.value!=='');ValuationRange.summarize(supplied.map(x=>Number(x.value)));
   if(data.estimates.some(x=>typeof x.value!=='string'||typeof x.label!=='string'||x.label.length>100))throw Error();
   currency.value=data.currency;data.estimates.forEach((x,i)=>{rows[i].value=x.value;document.querySelector('#label-'+i).value=x.label;});calculate();message.textContent='Shared inputs loaded. Their source, property, date and currency have not been verified.';
  }catch(e){clear();error.textContent='This shared scenario could not be read. Enter two to five valid estimates instead.';}
 }
})();
