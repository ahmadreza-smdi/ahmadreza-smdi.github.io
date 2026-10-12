/** Render only the guide's existing default example from its source in an offline DOM model. */
import vm from 'node:vm';
import fs from 'node:fs';
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
class Element {
  constructor(tag = 'div') { this.tag = tag; this.children = []; this.listeners = {}; this.value = ''; this.textContent = ''; this.className = ''; this.disabled = true; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  setAttribute() {}
  setCustomValidity() {}
  focus() {}
  reportValidity() {}
  html() { return `<${this.tag}${this.className ? ` class="${escape(this.className)}"` : ''}>${escape(this.textContent)}${this.children.map(child => child.html()).join('')}</${this.tag}>`; }
}
const keys = ['user', 'decision', 'action', 'evidence', 'availability', 'stakes', 'review', 'baseline', 'success'];
const defaults = { user: '', decision: '', action: '', evidence: '', availability: 'unknown', stakes: 'low', review: 'always', baseline: '', success: '' };
const nodes = Object.fromEntries(['decision-form', 'brief-content', 'status', 'download', 'print', 'interactive', 'brief-heading'].map(id => [id, new Element()]));
const form = nodes['decision-form'];
form.elements = Object.fromEntries(keys.map(key => [key, new Element()]));
form.reset = () => keys.forEach(key => { form.elements[key].value = defaults[key]; });
const examples = ['property', 'support', 'blank'].map(name => { const element = new Element('button'); element.dataset = { example: name }; return element; });
const startupControls = [...Object.values(form.elements), ...examples, nodes.download, nodes.print];
vm.runInNewContext(input.script, {
  document: { getElementById: id => nodes[id], querySelectorAll: selector => selector === '[data-example]' ? examples : selector === '[data-startup-control]' ? startupControls : [], createElement: tag => new Element(tag) },
  Blob, URL: { createObjectURL() { throw new Error('Startup rendering must not export'); }, revokeObjectURL() {} },
  setTimeout() { throw new Error('Startup rendering must not schedule work'); }, window: { print() { throw new Error('Startup rendering must not print'); } }
}, { timeout: 1000 });
if (nodes['brief-content'].children.length !== 6) throw new Error('Expected the six existing default brief sections');
const values = Object.fromEntries(keys.map(key => [key, form.elements[key].value]));
if (input.state_only) { process.stdout.write(JSON.stringify({ values, status: nodes.status.textContent, contentHTML: nodes['brief-content'].children.map(node => node.html()).join('') })); }
else {
  let page = input.html;
  for (const key of keys) {
    const value = escape(values[key]);
    if (['decision', 'evidence', 'success'].includes(key)) {
      page = page.replace(new RegExp(`(<textarea\\b[^>]*\\bid="${key}"[^>]*>)[\\s\\S]*?(</textarea>)`), (_, open, close) => open + value + close);
    } else if (['availability', 'stakes', 'review'].includes(key)) {
      page = page.replace(new RegExp(`(<select\\b[^>]*\\bid="${key}"[^>]*>)([\\s\\S]*?)(</select>)`), (_, open, options, close) => open + options.replace(/\sselected(?:="[^"]*")?/g, '').replace(/<option\b([^>]*\bvalue="([^"]+)"[^>]*)>/g, (tag, attributes, option) => `<option${attributes}${option === values[key] ? ' selected' : ''}>`) + close);
    } else {
      page = page.replace(new RegExp(`<input\\b[^>]*\\bid="${key}"[^>]*>`), tag => tag.replace(/\svalue="[^"]*"/g, '').replace(/>$/, ` value="${value}">`));
    }
  }
  page = page.replace(/(<p id="status"[^>]*>)[\s\S]*?(<\/p>)/, (_, open, close) => open + escape(nodes.status.textContent) + close);
  page = page.replace(/(<div id="brief-content">)[\s\S]*?(<\/div>)/, (_, open, close) => open + nodes['brief-content'].children.map(node => node.html()).join('') + close);
  page = page.replace(/(<div id="interactive")[^>]*>/, '$1>');
  const start = page.indexOf('<div id="interactive">'), end = page.indexOf('<section class="guide-outro">');
  if (start < 0 || end <= start) throw new Error('Missing bounded interactive region');
  const region = page.slice(start, end).replace(/<(input|textarea|select|button)\b([^>]*)>/g, (_, tag, attributes) => `<${tag}${attributes.replace(/\sdisabled(?:="[^"]*")?/g, '').replace(/\sdata-startup-control(?:="[^"]*")?/g, '')} disabled data-startup-control>`);
  page = page.slice(0, start) + region + page.slice(end);
  process.stdout.write(page);
}
