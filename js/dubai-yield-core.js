(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.DubaiYield=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const keys=['price','rent','vacancy','service','repairs','insurance','management','other','acquisition'];
 function calculate(input){
  const n={};for(const k of keys){const v=input[k];if(v===null||v===undefined||String(v).trim()==='')throw new Error('Enter '+k+'; an unknown amount is not zero.');n[k]=Number(v);if(!Number.isFinite(n[k])||n[k]<0)throw new Error('Use a finite, non-negative '+k+'.');}
  if(n.price<=0)throw new Error('Property price must be greater than zero.');
  if(n.vacancy>100)throw new Error('Vacancy / collection loss must be between 0 and 100%.');
  const collected=n.rent*(1-n.vacancy/100),operating=n.service+n.repairs+n.insurance+n.management+n.other,noi=collected-operating,allIn=n.price+n.acquisition;
  const out={collected,operating,noi,allIn,gross:n.rent/n.price*100,net:noi/n.price*100,onCost:noi/allIn*100};out.gap=out.gross-out.net;
  if(!Object.values(out).every(Number.isFinite))throw new Error('Inputs exceed the supported calculation range.');
  return out;
 }
 return {keys,calculate};
});
