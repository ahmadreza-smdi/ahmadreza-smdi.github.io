// Browser-local calculations. Missing values stay null; zero must be explicit.
export const VERIFIED_ON = "2026-10-11";
export const FEE_SOURCES = Object.freeze({
  sale: "https://dubailand.gov.ae/en/eservices/property-sale-registration",
  mortgage: "https://dubailand.gov.ae/en/eservices/request-for-mortgage-registration/",
  statute: "https://dlp.dubai.gov.ae/Legislation%20Reference/2013/ECR%2030%20of%202013.html",
  vat: "https://tax.gov.ae/en/faq.aspx?keyword=real+estate"
});
const MAP_FEES = Object.freeze({villa_apartment:250, unified_municipality:225, land_outside_municipality:100});
const sum = values => values.every(v => v !== null) ? values.reduce((a,b) => a+b,0) : null;
function reader(input) {
  const issues=[], cache=new Map();
  function issue(field,message,kind="missing") {
    if (!issues.some(x=>x.field===field)) issues.push({field,message,kind});
    return null;
  }
  function number(field,{positive=false,max=Infinity,label=field}={}) {
    if(cache.has(field)) return cache.get(field);
    const value=input[field];
    let out=value;
    if(value===null || value===undefined) out=issue(field,`Enter ${label}; use 0 only if it is known to be zero.`);
    else if(typeof value!=="number" || !Number.isFinite(value) || value<0 || (positive && value===0) || value>max)
      out=issue(field,`${label} must be a finite ${positive?"positive":"nonnegative"} number${max===Infinity?"":` no greater than ${max}`}.`,"invalid");
    cache.set(field,out);return out;
  }
  function choice(field,allowed,label=field) {
    const value=input[field];
    return allowed.includes(value)?value:issue(field,`Choose ${label}.`);
  }
  return {issues,issue,number,choice};
}
function finished(r,outputs,extra={}) {
  for(const [key,value] of Object.entries(outputs)) {
    if(typeof value==="number" && !Number.isFinite(value)) {
      outputs[key]=null;
      r.issue("arithmetic","The entered figures exceed the calculator's finite arithmetic range.","invalid");
    }
  }
  for(const item of extra.lineItems || []) {
    for(const key of ["total","buyerAmount"]) if(typeof item[key]==="number" && !Number.isFinite(item[key])) item[key]=null;
  }
  return {complete:r.issues.length===0,issues:r.issues,outputs,...extra};
}
export function calculateRental(input={}) {
  const r=reader(input), n=(field,opts)=>r.number(field,opts);
  const price=n("purchasePrice",{positive:true,label:"purchase price"});
  const rent=n("annualRent",{label:"annual potential rent"});
  const vacancy=n("vacancyPercent",{max:100,label:"vacancy/noncollection percentage"});
  const otherIncome=n("otherIncome",{label:"other annual cash receipts"});
  const operatingFields=["serviceCharges","repairs","insurance","management","otherOperating"];
  const operating=sum(operatingFields.map(field=>n(field)));
  const mode=r.choice("financing",["cash","mortgage"],"cash or mortgage financing");
  let loan=null,interest=null,principal=null;
  if(mode==="cash"){loan=0;interest=0;principal=0;}
  if(mode==="mortgage"){
    loan=n("loanProceeds",{positive:true,label:"loan funding before modelled costs"});
    interest=n("annualInterest",{label:"annual interest cash payment"});
    principal=n("annualPrincipal",{label:"annual principal cash payment"});
  }
  const annualCapex=n("annualCapex",{label:"annual capital spending"});
  const acquisition=n("acquisitionCosts",{label:"buyer-paid acquisition costs"});
  const initialCapex=n("initialCapex",{label:"initial capital spending"});
  const receipts=sum([rent,vacancy,otherIncome])===null?null:rent*(1-vacancy/100)+otherIncome;
  const noi=sum([receipts,operating])===null?null:receipts-operating;
  const debt=sum([interest,principal]);
  const annualCash=sum([noi,debt,annualCapex])===null?null:noi-debt-annualCapex;
  const invested=sum([price,loan,acquisition,initialCapex])===null?null:price-loan+acquisition+initialCapex;
  let cashOnCash=null;
  if(invested!==null && invested<=0) r.issue("initialCash","Initial cash invested must be positive to calculate cash-on-cash return.","invalid");
  else if(invested!==null && annualCash!==null) cashOnCash=annualCash/invested;
  return finished(r,{
    grossYield:price===null || rent===null?null:rent/price,
    effectiveReceipts:receipts,operatingCosts:operating,netOperatingIncome:noi,
    debtCashPayments:debt,annualCapitalSpending:annualCapex,annualCashFlow:annualCash,
    initialCashInvested:invested,cashOnCash
  },{basis:"Annual AED amounts; potential rent before vacancy. Principal is a cash payment, not operating expense."});
}
export function calculatePurchase(input={}) {
  const r=reader(input), n=(field,opts)=>r.number(field,opts);
  const scope=r.choice("scope",["existing_residential_completed"],"ordinary completed existing residential scope");
  const price=n("purchasePrice",{positive:true,label:"purchase price"});
  // Blank assessment explicitly means the entered price; never means zero.
  const value=input.assessedValue===null || input.assessedValue===undefined?price:
    n("assessedValue",{positive:true,label:"registered/assessed sale value"});
  const buyerShare=n("registrationBuyerPercent",{max:100,label:"buyer share of the total registration fee"});
  const shares={
    title:n("titleBuyerPercent",{max:100,label:"buyer share of title-deed fee"}),
    map:n("mapBuyerPercent",{max:100,label:"buyer share of map fee"}),
    admin:n("adminBuyerPercent",{max:100,label:"buyer share of knowledge/innovation fees"}),
    partner:n("partnerBuyerPercent",{max:100,label:"buyer share of sale partner fee"})
  };
  const map=r.choice("mapKind",Object.keys(MAP_FEES),"the map shown on the fee quote");
  const base=value===null?null:value>=500000?4000:2000;
  const lineItems=[];
  const add=(id,label,total,share,source)=> {
    const buyerAmount=total===null || share===null?null:total*share/100;
    lineItems.push({id,label,total,buyerPercent:share,buyerAmount,source});
    return buyerAmount;
  };
  add("sale_registration","Sale registration",value===null?null:0.04*value,buyerShare,"statute");
  add("title_deed","One sale title deed",250,shares.title,"sale");
  add("map","One applicable map",map===null?null:MAP_FEES[map],shares.map,"sale");
  add("knowledge_innovation","Knowledge and innovation",20,shares.admin,"sale");
  add("sale_partner","Sale partner fee including 5% VAT",base===null?null:base*1.05,shares.partner,"sale");
  const mode=r.choice("financing",["cash","mortgage"],"cash or mortgage financing");
  let loan=null;
  if(mode==="cash") loan=0;
  if(mode==="mortgage"){
    loan=n("loanProceeds",{positive:true,label:"loan funding before modelled fees"});
    const registeredDebt=n("mortgageDebt",{positive:true,label:"registered mortgage debt"});
    const mortgageShare=n("mortgageBuyerPercent",{max:100,label:"buyer share of mortgage registration"});
    add("mortgage_registration","Mortgage registration",registeredDebt===null?null:registeredDebt*0.0025,mortgageShare,"mortgage");
    const treatment=r.choice("mortgageFixedMode",["included","extra_quote"],"confirmed mortgage fixed-fee treatment");
    if(input.mortgageOverlapConfirmed!==true)
      r.issue("mortgageOverlapConfirmed","Confirm the quote contains no repeated sale partner, map or title-deed charges.");
    const additional=treatment===null?null:treatment==="included"?0:
      n("extraMortgageQuote",{label:"additional mortgage fixed/document quote, including VAT"});
    add("mortgage_extra_quote","Confirmed additional mortgage fixed/document costs",additional,100,"user_quote");
  }
  const variableFields=["brokerQuote","nocQuote","bankQuote","insuranceQuote","conveyancingQuote","otherQuote"];
  const quoteLabels=["Broker quote including VAT","Developer e-NOC quote","Bank/valuation quote","Upfront insurance quote","Conveyancing quote","Other buyer-paid purchase costs"];
  const variable=variableFields.map((field,i)=> {
    const amount=n(field,{label:quoteLabels[i]});
    return add(field,quoteLabels[i],amount,100,"user_quote");
  });
  const knownItems=lineItems.filter(x=>x.buyerAmount!==null);
  const knownSubtotal=knownItems.length?knownItems.reduce((a,b)=>a+b.buyerAmount,0):null;
  const subtotal=sum(lineItems.map(x=>x.buyerAmount));
  const feeTotal=r.issues.length===0 && scope!==null?subtotal:null;
  const requiredCash=feeTotal===null || price===null || loan===null?null:price-loan+feeTotal;
  return finished(r,{
    registrationValue:value,salePartnerBase:base,knownCostSubtotal:knownSubtotal,
    modeledBuyerCosts:feeTotal,requiredCash
  },{lineItems,verifiedOn:VERIFIED_ON,
    basis:"Completed existing residential transaction. Known subtotal is partial when inputs are missing; totals exclude unmodelled costs."});
}
export const FICTIONAL_RENTAL = Object.freeze({
  purchasePrice:1000000,annualRent:80000,vacancyPercent:5,otherIncome:0,
  serviceCharges:10000,repairs:3000,insurance:1000,management:4000,otherOperating:0,
  financing:"mortgage",loanProceeds:700000,annualInterest:30000,annualPrincipal:12000,
  annualCapex:2000,acquisitionCosts:50000,initialCapex:10000
});
export const FICTIONAL_PURCHASE = Object.freeze({
  scope:"existing_residential_completed",purchasePrice:1000000,assessedValue:null,
  registrationBuyerPercent:50,titleBuyerPercent:100,mapBuyerPercent:100,
  adminBuyerPercent:100,partnerBuyerPercent:100,mapKind:"villa_apartment",
  financing:"cash",loanProceeds:null,mortgageFixedMode:null,
  brokerQuote:0,nocQuote:0,bankQuote:0,insuranceQuote:0,conveyancingQuote:0,otherQuote:0
});

