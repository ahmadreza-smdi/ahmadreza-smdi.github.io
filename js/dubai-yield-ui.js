document.addEventListener('DOMContentLoaded',()=>{
 'use strict';const api=window.DubaiYield,form=document.getElementById('yield-form'),error=document.getElementById('yield-error'),results=document.getElementById('yield-results');
 const example={price:1000000,rent:120000,vacancy:5,service:15000,repairs:5000,insurance:2000,management:5000,other:0,acquisition:50000};
 const number=new Intl.NumberFormat('en-AE',{maximumFractionDigits:2});
 function values(){return Object.fromEntries(api.keys.map(k=>[k,document.getElementById(k).value]));}
 function run(){try{const out=api.calculate(values());for(const [k,v] of Object.entries(out)){const el=document.querySelector('[data-yield="'+k+'"]');if(el)el.textContent=number.format(v)+(['gross','net','onCost'].includes(k)?'%':k==='gap'?' percentage points':' AED');}error.textContent='';results.hidden=false;return true;}catch(e){error.textContent=e.message;results.hidden=true;return false;}}
 form.addEventListener('submit',e=>{e.preventDefault();run();});
 form.addEventListener('input',()=>{results.hidden=true;document.getElementById('yield-share').value='';});
 document.getElementById('yield-example').addEventListener('click',()=>{for(const k of api.keys)document.getElementById(k).value=example[k];run();});
 document.getElementById('yield-clear').addEventListener('click',()=>{form.reset();results.hidden=true;error.textContent='';document.getElementById('yield-share').value='';});
 document.getElementById('yield-share-button').addEventListener('click',()=>{if(!run())return;const q=new URLSearchParams(values());document.getElementById('yield-share').value='https://a-samadi.com/tools/dubai-rental-yield.html#'+q.toString();});
 document.getElementById('yield-print').addEventListener('click',()=>{if(run())window.print();});
 const q=new URLSearchParams(location.hash.slice(1));if(api.keys.every(k=>q.has(k))){for(const k of api.keys)document.getElementById(k).value=q.get(k);run();}
});
