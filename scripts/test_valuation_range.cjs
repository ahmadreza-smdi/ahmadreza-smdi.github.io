const assert = require('node:assert/strict');
const {summarize} = require('../js/valuation-range-core.js');
// Three independently worked fictional examples: close, skewed, and even-count median.
let a = summarize([950000,1000000,1050000]);
assert.deepEqual([a.low,a.high,a.median,a.spread],[950000,1050000,1000000,10]);
assert.deepEqual(a.flagged,[false,false,false]);
let b = summarize([800000,1000000,1400000]);
assert.deepEqual([b.low,b.high,b.median,b.spread],[800000,1400000,1000000,60]);
assert.deepEqual(b.flagged,[true,false,true]);
let c = summarize([900000,1000000,1100000,1200000]);
assert.equal(c.median,1050000);assert.ok(Math.abs(c.spread-28.57142857142857)<1e-10);
assert.deepEqual(c.flagged,[true,false,false,true]);
// Boundary behavior: exactly ten percent is not "more than" ten percent.
assert.deepEqual(summarize([90,100,110]).flagged,[false,false,false]);
assert.deepEqual(summarize([90,100,110.01]).flagged,[false,false,true]);
assert.equal(summarize([200,200]).spread,0);
assert.equal(summarize([1e308,1e308]).median,1e308);
for(const x of [[],[1],[1,2,3,4,5,6],[0,10],[-1,10],[NaN,10],[Infinity,10],['10',20],[1e-300,2e-300,1e308]])assert.throws(()=>summarize(x));
console.log('PASS valuation range: three worked examples; even median, strict threshold, duplicates, finite/positive/count/overflow guards');
