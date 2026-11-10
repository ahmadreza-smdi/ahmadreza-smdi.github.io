const assert=require('node:assert/strict');const {calculate}=require('../js/dubai-yield-core.js');
const fixture={price:1000000,rent:120000,vacancy:5,service:15000,repairs:5000,insurance:2000,management:5000,other:0,acquisition:50000};
let r=calculate(fixture);assert.equal(r.gross,12);assert.equal(r.collected,114000);assert.equal(r.noi,87000);assert.equal(r.net,8.7);assert.ok(Math.abs(r.onCost-8.285714285714286)<1e-10);
r=calculate({...fixture,vacancy:100});assert.equal(r.collected,0);assert.equal(r.noi,-27000);assert.equal(r.net,-2.7);
r=calculate({...fixture,rent:0,service:0,repairs:0,insurance:0,management:0,other:0,acquisition:0});assert.equal(r.net,0);assert.equal(r.onCost,0);
for(const patch of [{service:''},{rent:null},{price:0},{vacancy:101},{other:-1},{price:Infinity},{rent:1e308,price:1e-308}])assert.throws(()=>calculate({...fixture,...patch}));
assert.equal(calculate({...fixture,acquisition:1000000}).net,8.7);assert.equal(calculate({...fixture,acquisition:1000000}).onCost,4.35);
console.log('Dubai yield: 3 worked scenarios, unknown/zero/negative/overflow/range checks and denominator separation PASS');
