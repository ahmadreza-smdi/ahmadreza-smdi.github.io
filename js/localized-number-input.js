// Keep native number validation, stepping, and the user's insertion point.
(() => {
  'use strict';
  const isNumberField = target => target instanceof HTMLInputElement && target.type === 'number';

  function insertLocalized(event, text) {
    if (!isNumberField(event.target) || !text || !/[٠-٩۰-۹٫٬,]/u.test(text)) return;

    let normalized = text.replace(/[٠-٩۰-۹]/gu, digit =>
      String(digit.charCodeAt(0) - (digit <= '٩' ? 0x660 : 0x6f0))
    ).replace(/٫/gu, '.');

    if (/[,٬]/u.test(normalized)) {
      // A one-character separator can be a native locale decimal keystroke.
      if (normalized.length === 1) return;
      // Only remove separators from complete, unambiguous thousands groups.
      if (!/^[+-]?\d{1,3}(?:[,٬]\d{3})+(?:\.\d+)?$/u.test(normalized)) {
        event.preventDefault();
        return;
      }
      normalized = normalized.replace(/[,٬]/gu, '');
    }
    if (normalized === text) return;
    event.preventDefault();
    // Number inputs do not expose selectionStart or setRangeText. Native insertion
    // replaces the selection, keeps undo available, and sends the normal input event.
    document.execCommand('insertText', false, normalized);
  }

  document.addEventListener('beforeinput', event => {
    if (!event.isComposing && event.cancelable) insertLocalized(event, event.data);
  });
  document.addEventListener('paste', event => {
    if (event.clipboardData) insertLocalized(event, event.clipboardData.getData('text/plain'));
  });
})();

