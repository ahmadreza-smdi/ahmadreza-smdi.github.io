import {initializeSharing} from "./sharing.mjs?v=20261015-share1";
import {calculateRental,calculatePurchase,FICTIONAL_RENTAL,FICTIONAL_PURCHASE} from "./calculations.mjs";
const page=document.querySelector("[data-page]"), form=document.querySelector("[data-calculator]");
if(form){
 const isRental=page.dataset.page==="rental",calculate=isRental?calculateRental:calculatePurchase;
 const money=new Intl.NumberFormat("en-AE",{style:"currency",currency:"AED",minimumFractionDigits:2,maximumFractionDigits:2});
 const percent=new Intl.NumberFormat("en-AE",{style:"percent",minimumFractionDigits:1,maximumFractionDigits:2});
 let showIssues=false;
 function values(){
  const data={};
  for(const el of form.elements){
   if(!el.name)continue;
   if(el.type==="checkbox")data[el.name]=el.checked;
   else if(el.type==="number")data[el.name]=el.value.trim()===""?null:Number(el.value);
   else data[el.name]=el.value||null;
  }
  return data;
 }
 function sync(){
  const mortgage=form.elements.financing.value==="mortgage";
  for(const section of form.querySelectorAll("[data-mortgage]")){
   section.hidden=!mortgage;
   for(const el of section.querySelectorAll("input,select"))el.disabled=!mortgage;
  }
  const extra=form.querySelector("[data-extra-quote]");
  if(extra){extra.hidden=!mortgage || form.elements.mortgageFixedMode.value!=="extra_quote";extra.querySelector("input").disabled=extra.hidden;}
 }
 function render(){
  sync();const result=calculate(values());
  page.querySelectorAll("[data-output]").forEach(el=>{
   const value=result.outputs[el.dataset.output];
   el.textContent=value===null || value===undefined?"Not available":
    ["grossYield","cashOnCash"].includes(el.dataset.output)?percent.format(value):money.format(value);
   el.classList.toggle("negative",typeof value==="number" && value<0);
  });
  const status=page.querySelector("[data-status]");
  status.textContent=result.complete?"Calculated from the figures entered.":
   showIssues?`Complete or correct ${result.issues.length} input${result.issues.length===1?"":"s"}; unavailable totals are not zero.`:"Enter your figures. Blank inputs remain unknown.";
  const list=page.querySelector("[data-issues]");list.replaceChildren();
  const issueDetails=page.querySelector("[data-issue-details]");
  issueDetails.hidden=!showIssues || result.complete;
  page.querySelector("[data-issue-count]").textContent=`Inputs still needed (${result.issues.length})`;
  if(showIssues){
   for(const issue of result.issues){const li=document.createElement("li");li.textContent=issue.message;list.append(li);}
  }
  for(const el of form.querySelectorAll(".field-error")){el.classList.remove("field-error");el.removeAttribute("aria-invalid");}
  if(showIssues)for(const issue of result.issues){
   const el=form.elements.namedItem(issue.field);
   if(el){el.classList.add("field-error");el.setAttribute("aria-invalid","true");}
  }
  const items=page.querySelector("[data-line-items]");
  if(items){
   items.replaceChildren();
   for(const item of result.lineItems){
    const row=document.createElement("div");row.className="metric";
    const dt=document.createElement("dt");dt.textContent=item.label;
    const dd=document.createElement("dd");dd.textContent=item.buyerAmount===null?"Unknown":money.format(item.buyerAmount);
    row.append(dt,dd);items.append(row);
   }
  }
  page.dispatchEvent(new Event("calculator:render"));
 }
 form.addEventListener("submit",event=>{event.preventDefault();showIssues=true;render();});
 form.addEventListener("input",render);form.addEventListener("change",render);
 form.querySelector("[data-example]").addEventListener("click",()=>{
  const fixture=isRental?FICTIONAL_RENTAL:FICTIONAL_PURCHASE;
  form.reset();for(const [key,value] of Object.entries(fixture)){
   const el=form.elements.namedItem(key);if(!el)continue;
   if(el.type==="checkbox")el.checked=value===true;else el.value=value===null?"":String(value);
  }
  form.querySelector("[data-example-note]").hidden=false;showIssues=true;render();
 });
 form.querySelector("[data-clear]").addEventListener("click",()=>{
  form.reset();form.querySelector("[data-example-note]").hidden=true;showIssues=false;render();
 });
 const allBuyer=form.querySelector("[data-all-buyer]");
 if(allBuyer)allBuyer.addEventListener("click",()=>{
  for(const key of ["titleBuyerPercent","mapBuyerPercent","adminBuyerPercent","partnerBuyerPercent"])form.elements[key].value="100";
  render();
 });
 page.addEventListener("calculator:restore",()=>{showIssues=true;render();});
 initializeSharing(page,form);form.hidden=false;render();
}

