// URL fragments are explicit portable inputs, never evidence of recipient review.
export function cleanInputs(inputs, fields) {
  const out=Object.create(null);
  for(const f of fields){
    const v=Object.hasOwn(inputs,f.name)?inputs[f.name]:null;
    if(f.type==='checkbox'){out[f.name]=false;continue;}
    if(v===null || v===undefined || v===''){out[f.name]=null;continue;}
    if(f.type==='number'){
      if(typeof v!=='number'||!Number.isFinite(v)||v<0||(f.max!==undefined&&v>f.max))throw Error(`Invalid saved input: ${f.name}`);
      out[f.name]=v;
    }else{
      if(typeof v!=='string'||!f.options.includes(v))throw Error(`Invalid saved choice: ${f.name}`);
      out[f.name]=v;
    }
  }
  return out;
}
export function encodeState(kind,inputs,fields,origin='user-inputs'){
  if(!['rental','purchase'].includes(kind))throw Error('Unknown calculator');
  if(!['user-inputs','fictional-example'].includes(origin))throw Error('Unknown input origin');
  return '#calc='+encodeURIComponent(JSON.stringify({v:1,kind,origin,inputs:cleanInputs(inputs,fields)}));
}
export function decodeState(hash,kind,fields){
  if(!hash.startsWith('#calc='))return null;
  if(hash.length>12000)throw Error('Saved link is too long.');
  let payload;try{payload=JSON.parse(decodeURIComponent(hash.slice(6)));}catch{throw Error('Saved link could not be read.');}
  if(payload?.v!==1||payload.kind!==kind||!payload.inputs||typeof payload.inputs!=='object'||Array.isArray(payload.inputs))throw Error('Saved link does not match this calculator.');
  const inputs=cleanInputs(payload.inputs,fields);
  Object.defineProperty(inputs,'origin',{value:payload.origin==='fictional-example'?'fictional-example':'user-inputs'});
  return inputs;
}
