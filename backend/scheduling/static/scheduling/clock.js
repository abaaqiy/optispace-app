/* Wall-clock presentation only. API and review payloads keep canonical HH:MM. */
(() => {
  function format(value) {
    const match = /^(\d{2}):([0-5]\d)(?::([0-5]\d))?$/.exec(value || '');
    if (!match || Number(match[1]) > 23) return value || '';
    const hour = Number(match[1]);
    return `${hour % 12 || 12}:${match[2]}${match[3] && match[3] !== '00' ? ':' + match[3] : ''} ${hour >= 12 ? 'PM' : 'AM'}`;
  }
  function parse(value) {
    const match = /^(0?[1-9]|1[0-2]):([0-5]\d)\s*([AP]M)$/i.exec((value || '').trim());
    if (!match) return '';
    const hour = Number(match[1]) % 12 + (match[3].toUpperCase() === 'PM' ? 12 : 0);
    return `${String(hour).padStart(2, '0')}:${match[2]}`;
  }
  function input(el, value, label) {
    el.type = 'text'; el.placeholder = '2:30 PM'; el.value = format(value);
    el.setAttribute('aria-label', label + ' (AM/PM)');
    el.setAttribute('autocomplete', 'off');
    el.addEventListener('input', () => el.setCustomValidity(el.value && !parse(el.value) ? 'Enter a time such as 2:30 PM, including AM or PM.' : ''));
    el.addEventListener('blur', () => { const clock = parse(el.value); if (clock) el.value = format(clock); });
    return el;
  }
  globalThis.OptispaceClock = { format, parse, input };
})();
