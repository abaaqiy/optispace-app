/* Exact code lookup across all sourced departments; never infer a title from OCR. */
(() => {
  const codeKey = value => String(value || '').toUpperCase().replace(/\s/g, '');
  function lookup(code, catalogue, sources = {}) {
    const key = codeKey(code);
    if (!/^[A-Z]{2,5}\d{3}$/.test(key)) return [];
    const matches = catalogue.filter(entry => codeKey(entry.code) === key)
      .map(entry => ({ ...sources[entry.source_id], ...entry }));
    const groups = new Map();
    matches.forEach(entry => {
      // Group repeated evidence only when title, department AND programme agree.
      const signature = [entry.title, entry.department || '', entry.programme || '']
        .map(value => value.toLocaleLowerCase().replace(/\s+/g, ' ').trim()).join('|');
      if (groups.has(signature)) groups.get(signature).evidence.push(entry);
      else groups.set(signature, { ...entry, evidence: [entry] });
    });
    return Array.from(groups.values());
  }
  function renderCandidates(root, matches, currentTitle, onUse) {
    function element(tag, text, parent) {
      const el = root.ownerDocument.createElement(tag);
      if (text !== undefined) el.textContent = text;
      parent.append(el); return el;
    }
    element('p', matches.length > 1 ? 'Different titles or programmes match this code. Check the handbook page and choose the one that applies; a handbook can contain conflicting lists.' : 'Exact course-code match in a source. Check that its curriculum applies to this course.', root);
    matches.forEach(item => {
      const candidate = element('div', undefined, root);
      element('strong', `${item.code} — ${item.title}`, candidate);
      element('p', `${item.department || 'Department must be confirmed'} · ${item.faculty || ''}${item.programme ? ` · ${item.programme}` : ''}`, candidate);
      item.evidence.forEach(evidence => {
        const label = `${evidence.source_title}${evidence.page ? `, PDF page ${evidence.page}` : ''} · ${evidence.edition}`;
        const line = element('p', undefined, candidate);
        if (evidence.source_url) {
          const link = element('a', label, line); link.href = `${evidence.source_url}${evidence.page ? `#page=${evidence.page}` : ''}`; link.target = '_blank'; link.rel = 'noopener noreferrer';
        } else element('span', `${label} — reference file available in local development`, line);
        if (evidence.notes) element('p', evidence.notes, candidate).className = 'review-note';
      });
      const acknowledgement = element('label', undefined, candidate);
      const applicable = element('input', undefined, acknowledgement); applicable.type = 'checkbox';
      acknowledgement.append(root.ownerDocument.createTextNode(' I checked that this source applies to this programme and academic session.'));
      const use = element('button', currentTitle && currentTitle !== item.title ? 'Replace title with this suggestion' : 'Use this title', candidate); use.type = 'button';
      use.disabled = true;
      applicable.addEventListener('change', () => { use.disabled = !applicable.checked; });
      use.addEventListener('click', () => { if (applicable.checked) onUse(item); });
    });
  }
  const api = { codeKey, lookup, renderCandidates };
  if (typeof window !== 'undefined') window.OptispaceCourseSuggestions = api;
})();
