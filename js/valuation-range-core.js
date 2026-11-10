/* Educational arithmetic; no estimate selection, valuation or source verification. */
(function (root) {
  'use strict';
  function summarize(estimates) {
    if (!Array.isArray(estimates) || estimates.length < 2 || estimates.length > 5) throw new Error('Enter between two and five estimates.');
    if (estimates.some(v => typeof v !== 'number' || !Number.isFinite(v) || v <= 0)) throw new Error('Every estimate must be a finite number greater than zero.');
    const sorted = estimates.slice().sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    const median = sorted.length % 2 ? sorted[middle] : sorted[middle - 1] / 2 + sorted[middle] / 2;
    const low = sorted[0], high = sorted[sorted.length - 1];
    const spread = (high - low) / median * 100;
    const deviations = estimates.map(v => (v / median - 1) * 100);
    if (![median, spread, ...deviations].every(Number.isFinite)) throw new Error('This range exceeds the calculator’s numeric precision. Use amounts at a comparable scale.');
    const flagged = deviations.map(v => Math.abs(v) > 10 + 1e-10);
    let next = 'The entered estimates are within a 10% overall spread. Check the property identity, valuation dates, condition, area definitions and source independence anyway. Agreement is not evidence of accuracy.';
    if (spread > 10 + 1e-10) next = 'The overall spread exceeds 10%. Reconcile the property identifiers, dates, area definitions, comparable evidence and assumptions before choosing a value. The median does not decide which source is right.';
    if (flagged.some(Boolean)) next += ' At least one estimate is more than 10% from the median: inspect its basis; do not automatically discard it.';
    next += ' For a lending, contractual or other consequential decision, confirm the required valuation process with the responsible professional.';
    return {low, high, median, spread, deviations, flagged, next};
  }
  if (typeof module === 'object' && module.exports) module.exports = {summarize};
  else root.ValuationRange = Object.freeze({summarize});
})(typeof window === 'object' ? window : globalThis);
