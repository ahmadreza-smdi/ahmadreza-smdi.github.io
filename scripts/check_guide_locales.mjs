import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { Blob } from 'node:buffer';
const root = new URL('../', import.meta.url);
class Element {
  constructor(){this.children=[];this.listeners={};this.value='';this.textContent='';}
  append(...items){this.children.push(...items);}
  replaceChildren(){this.children=[];}
  addEventListener(type,fn){this.listeners[type]=fn;}
  setAttribute(){}
  setCustomValidity(){}
  reportValidity(){}
  focus(){}
  click(){this.listeners.click?.();}
}
for(const lang of ['en','fa','ar']){
  const suffix=lang==='en'?'':`-${lang}`;
  const source=fs.readFileSync(new URL(`js/decision-guide${suffix}.js`,root),'utf8');
  const nodes=Object.fromEntries(['decision-form','brief-content','status','download','print','interactive','brief-heading'].map(id=>[id,new Element()]));
  const form=nodes['decision-form'];
  form.elements=Object.fromEntries(['user','decision','action','evidence','availability','stakes','review','baseline','success'].map(id=>[id,new Element()]));
  form.reset=()=>Object.values(form.elements).forEach(el=>{el.value='';});
  const examples=['property','support','blank'].map(example=>Object.assign(new Element(),{dataset:{example}}));
  let downloaded;
  const context={document:{getElementById:id=>nodes[id],querySelectorAll:()=>examples,createElement:()=>new Element()},Blob,URL:{createObjectURL:blob=>{downloaded=blob;return 'blob:test';},revokeObjectURL(){}},setTimeout:fn=>fn(),window:{print(){}}};
  vm.runInNewContext(source,context);
  assert.equal(nodes.interactive.hidden,false);
  for(const example of examples.slice(0,2)){
    example.click();
    for(const availability of ['unknown','partial','ready'])for(const stakes of ['low','high'])for(const review of ['always','exceptions','none']){
      Object.assign(form.elements.availability,{value:availability});
      Object.assign(form.elements.stakes,{value:stakes});
      Object.assign(form.elements.review,{value:review});
      form.listeners.submit({preventDefault(){}});
      assert.equal(nodes['brief-content'].children.length,6);
      nodes.download.click();
      const text=await downloaded.text();
      assert.ok(text.includes(`https://a-samadi.com/${lang==='en'?'':lang+'/'}tools/before-you-build-ai.html`));
      assert.ok(!text.includes('undefined'));
      if(lang!=='en')assert.ok(!/Choose a small|Resolve first|Check the evidence|Proceed only|A decision brief/.test(text));
    }
  }
  examples[2].click();
  assert.equal(nodes.download.disabled,true);
  assert.equal(nodes['brief-content'].children.length,0);
  console.log(`PASS ${lang}: examples, 36 branch combinations, localized export, blank state`);
}
