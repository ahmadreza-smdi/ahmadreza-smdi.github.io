'use strict';
(() => {
  const form = document.getElementById('decision-form');
  const content = document.getElementById('brief-content');
  const status = document.getElementById('status');
  const keys = ['user', 'decision', 'action', 'evidence', 'availability', 'stakes', 'review', 'baseline', 'success'];
  const examples = {
    property: { user: 'A property researcher', decision: 'Which properties deserve a closer investigation before an investor commits more time?', action: 'Shortlist candidates and request missing information or a manual inspection.', evidence: 'Dated property imagery, relevant property attributes and source provenance. Record what the imagery cannot establish.', availability: 'partial', stakes: 'medium', review: 'always', baseline: 'A researcher checks each listing and builds a shortlist manually.', success: 'Reduce research time while retaining useful candidates, with missing evidence visible and review effort included.' },
    support: { user: 'A customer support lead', decision: 'Which incoming requests need specialist attention before the next triage review?', action: 'Route a reviewed request to the right team with its supporting context.', evidence: 'The request text, relevant product documentation and confirmed examples of past routing decisions, with permission to use them.', availability: 'unknown', stakes: 'low', review: 'exceptions', baseline: 'A support lead reads the queue and assigns each request manually.', success: 'Reduce routing effort without increasing missed urgent requests or time spent correcting assignments.' }
  };
  let briefText = '';
  let dirty = false;
  function values() { return Object.fromEntries(keys.map(key => [key, form.elements[key].value.trim()])); }
  function section(title, body, ordered = false) {
    const wrap = document.createElement('section'); wrap.className = 'brief-section';
    const h = document.createElement('h3'); h.textContent = title; wrap.append(h);
    if (ordered) { const list = document.createElement('ol'); body.forEach(text => { const li = document.createElement('li'); li.textContent = text; list.append(li); }); wrap.append(list); }
    else { const p = document.createElement('p'); p.textContent = body; wrap.append(p); }
    content.append(wrap);
    return title.toUpperCase() + '\n' + (ordered ? body.map((s, i) => `${i + 1}. ${s}`).join('\n') : body);
  }
  function build(message) {
    const v = values();
    content.replaceChildren();
    const blocker = v.availability === 'unknown' ? 'Check the evidence before testing the model. Confirm access, permitted use, freshness and coverage; write down what remains unknown.' : v.availability === 'partial' ? 'Make the gaps visible. Identify missing sources and define when the tool must ask for information or hand the decision back to a person.' : 'Test the evidence against real cases. Availability does not establish accuracy or representativeness; inspect provenance and difficult cases.';
    const review = v.stakes === 'high' ? 'Keep this first experiment offline, with a qualified person reviewing every result. Document serious failure cases and escalation conditions before considering live use.' : v.review === 'none' ? 'Add a review step to the first experiment. A person should inspect the evidence and errors before outputs trigger action.' : v.review === 'exceptions' ? 'Review every result in the first experiment, including unflagged cases. Check whether the exception rules miss errors before relying on them.' : 'Keep the reviewer in the test. Record corrections and the time needed to review each result, alongside the model output.';
    const parts = [section('01 / The decision', `${v.user}\n\n${v.decision}`), section('The next action', v.action), section('02 / The evidence', v.evidence), section('Resolve first', blocker + '\n\n' + review), section('03 / The smallest useful experiment', [
      `Choose a small, explicitly scoped set of cases for this decision. Include typical cases, missing evidence and plausible failures. Do not treat a small pilot as proof of broad reliability.`,
      `Establish the baseline: ${v.baseline} Record time, outcomes and correction effort.`,
      `Prepare evidence-backed suggestions for the same cases, manually or with a simple prototype. ${review}`,
      `Compare against your criterion: ${v.success} Set measurable pass and stop conditions before testing; include delivery and review costs.`
    ], true), section('Proceed only when', 'The evidence supports the intended action, failures have a clear fallback, and the combined workflow improves on the baseline. If it does not, narrow the decision or revisit the inputs.')];
    briefText = 'BEFORE YOU BUILD THE AI\nA decision brief · Ahmadreza Samadi\n\n' + parts.join('\n\n') + '\n\nA structured thinking aid; not a validated assessment.\nhttps://a-samadi.com/tools/before-you-build-ai.html\n';
    dirty = false; status.textContent = message;
    document.getElementById('download').disabled = false; document.getElementById('print').disabled = false;
  }
  function load(name) {
    form.reset(); keys.forEach(key => { form.elements[key].setCustomValidity(''); if (examples[name]) form.elements[key].value = examples[name][key]; });
    document.querySelectorAll('[data-example]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.example === name)));
    if (name === 'blank') { content.replaceChildren(); briefText = ''; dirty = true; status.textContent = 'Fill in the worksheet, then build your brief.'; document.getElementById('download').disabled = true; document.getElementById('print').disabled = true; form.elements.user.focus(); }
    else build('Illustrative example loaded. Change any detail, then rebuild your brief.');
  }
  form.addEventListener('input', () => { dirty = true; status.textContent = 'Your inputs have changed. Rebuild the brief to include them.'; document.getElementById('download').disabled = true; document.getElementById('print').disabled = true; document.querySelectorAll('[data-example]').forEach(button => button.setAttribute('aria-pressed', 'false')); });
  form.addEventListener('submit', event => { event.preventDefault(); const empty = keys.find(key => !form.elements[key].value.trim()); if (empty) { form.elements[empty].setCustomValidity('Please add a specific detail.'); form.elements[empty].reportValidity(); form.elements[empty].addEventListener('input', () => form.elements[empty].setCustomValidity(''), { once: true }); return; } build('Brief updated. Ready to export or print.'); document.getElementById('brief-heading').focus(); });
  document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => load(button.dataset.example)));
  document.getElementById('download').addEventListener('click', () => { if (dirty || !briefText) return; const url = URL.createObjectURL(new Blob([briefText], { type: 'text/plain;charset=utf-8' })); const link = document.createElement('a'); link.href = url; link.download = 'decision-brief-ahmadreza-samadi.txt'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); status.textContent = 'Brief exported as a text file.'; });
  document.getElementById('print').addEventListener('click', () => { if (!dirty) window.print(); });
  document.getElementById('interactive').hidden = false;
  load('property');
})();
