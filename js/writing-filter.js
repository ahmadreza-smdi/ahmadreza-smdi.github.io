(() => {
  'use strict';
  const form = document.querySelector('.writing-filter');
  if (!form) return;
  const input = form.querySelector('input');
  const clear = form.querySelector('button');
  const count = form.querySelector('[data-count-template]');
  const empty = document.querySelector('.writing-empty');
  const topics = document.querySelector('nav[aria-labelledby="writing-topics-heading"]');
  const cards = Array.from(document.querySelectorAll('main > article'));
  if (!input || !clear || !count || !empty || !cards.length) return;

  // Match visible titles and summaries, including common Persian/Arabic input variants.
  const normalize = text => text.normalize('NFKD').toLowerCase()
    .replace(/\p{M}/gu, '').replace(/[يى]/g, 'ی').replace(/ك/g, 'ک')
    .replace(/[٠-٩]/g, digit => String(digit.charCodeAt(0) - 1632))
    .replace(/[۰-۹]/g, digit => String(digit.charCodeAt(0) - 1776))
    .replace(/[\u200c\u200d\u0640]/g, '').replace(/\s+/g, ' ').trim();
  const searchable = cards.map(card => normalize(Array.from(
    card.querySelectorAll('h2, p:not(.byline):not(:last-child)')
  ).map(node => node.textContent).join(' ')));
  const numbers = new Intl.NumberFormat(document.documentElement.lang === 'ar' ? 'ar-u-nu-arab' : document.documentElement.lang);
  const template = count.dataset.countTemplate;

  const update = () => {
    const terms = normalize(input.value).split(' ').filter(Boolean);
    // Latin keywords match word starts; short terms such as AI match whole words.
    const matchers = terms.map(term => {
      const word = /^[a-z0-9]+$/.test(term)
        ? new RegExp('\\b' + term + (term.length <= 2 ? '\\b' : '')) : null;
      return text => word ? word.test(text) : text.includes(term);
    });
    if (topics) topics.hidden = terms.length > 0;
    let visible = 0;
    cards.forEach((card, index) => {
      const matches = matchers.every(matches => matches(searchable[index]));
      card.hidden = !matches;
      if (matches) visible += 1;
    });
    count.textContent = template.replace('{count}', numbers.format(visible))
      .replace('{total}', numbers.format(cards.length));
    empty.hidden = visible !== 0;
    clear.disabled = input.value.length === 0;
  };
  form.addEventListener('submit', event => event.preventDefault());
  form.addEventListener('reset', event => {
    event.preventDefault();
    input.value = '';
    update();
    input.focus();
  });
  input.addEventListener('input', event => {
    if (!event.isComposing) update();
  });
  input.addEventListener('compositionend', update);
  window.addEventListener('pageshow', update);
  update();
  form.hidden = false;
})();
